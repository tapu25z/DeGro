from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import asdict
from typing import Any

import z3

from .compiler_z3 import UnsupportedExpression, compile_spec, model_value
from .determinacy import (
    CheckStatus,
    check_minimal_target_determinacy,
    check_target_determinacy,
    find_feasible_pair,
)
from .grounding import validate_repair
from .modelspec import Constraint, ModelSpec


METHODS = (
    "self_review",
    "grounded_self_review",
    "nonunique",
    "nonunique_grounding",
    "random_pair",
    "target_witness",
    "minimal_witness",
    "minimal_witness_grounding",
    "targetcheck",
)
NONUNIQUE_VERDICT = "\n\nSolver verdict: the target is not uniquely determined by the current constraints."
GROUNDING_RULE = (
    "\n\nGrounding rule: for ADD_CONSTRAINT, source_span must be an exact contiguous substring "
    "of the original problem that directly supports the expression. Otherwise ABSTAIN."
)
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["ADD_CONSTRAINT", "ABSTAIN"]},
        "source_span": {"type": ["string", "null"]},
        "constraint": {"type": ["string", "null"]},
    },
    "required": ["decision", "source_span", "constraint"],
    "additionalProperties": False,
}


def _spec_text(spec: ModelSpec) -> str:
    return "\n".join(f"- {constraint.expression}" for constraint in spec.constraints)


def build_prompt(method: str, row: dict[str, Any]) -> str:
    spec = ModelSpec.from_dict(row["spec"])
    common = f"""You audit a mathematical formalization.
Original problem:
{row['problem']}

Current constraints:
{_spec_text(spec)}

Target: {spec.target}

Return exactly one JSON object with these three top-level keys and no others:
{{"decision":"ADD_CONSTRAINT","source_span":"exact quote","constraint":"x == 1"}}
or
{{"decision":"ABSTAIN","source_span":null,"constraint":null}}
Never return an array, a constraints key, or a type key. ADD_CONSTRAINT means the source contains a missing condition; use a Python-style expression with ==. ABSTAIN means the source does not justify any missing condition. Do not invent assumptions."""
    if method == "self_review":
        return common
    if method == "grounded_self_review":
        return common + GROUNDING_RULE
    if method == "nonunique":
        return common + NONUNIQUE_VERDICT
    if method == "nonunique_grounding":
        return common + NONUNIQUE_VERDICT + GROUNDING_RULE
    if method == "random_pair":
        seed = int(hashlib.sha256(row["pair_id"].encode()).hexdigest()[:8], 16)
        result = find_feasible_pair(spec, random_seed=seed)
        if result.status != CheckStatus.AMBIGUOUS:
            raise ValueError(f"expected two feasible assignments, received {result.status}")
        pair = (
            "\n\nTwo arbitrary distinct assignments satisfy the current constraints. "
            "They were not selected based on the target."
            f"\nFeasible assignment A: {json.dumps(result.witness_1, sort_keys=True)}"
            f"\nFeasible assignment B: {json.dumps(result.witness_2, sort_keys=True)}"
        )
        return common + pair
    uses_minimal_witness = method in {"minimal_witness", "minimal_witness_grounding"}
    result = check_minimal_target_determinacy(spec) if uses_minimal_witness else check_target_determinacy(spec)
    if result.status != CheckStatus.AMBIGUOUS:
        raise ValueError(f"expected ambiguity, received {result.status}")
    witness_label = "Minimal target-divergent" if uses_minimal_witness else "Target-divergent"
    witness = (
        "\n\nBoth assignments satisfy the current constraints but disagree on the target."
        f"\nWitness selection: {witness_label}."
        f"\nWitness A: {json.dumps(result.witness_1, sort_keys=True)}"
        f"\nWitness B: {json.dumps(result.witness_2, sort_keys=True)}"
        f"\nTarget values: {result.witness_1[spec.target]} and {result.witness_2[spec.target]}."
    )
    if method in {"target_witness", "minimal_witness"}:
        return common + witness
    if method in {"minimal_witness_grounding", "targetcheck"}:
        return common + witness + GROUNDING_RULE
    raise ValueError(f"unknown method: {method}")


def prompt_hash() -> str:
    payload = {
        "methods": METHODS,
        "output_schema": OUTPUT_SCHEMA,
        "nonunique_verdict": NONUNIQUE_VERDICT,
        "grounding_rule": GROUNDING_RULE,
        "build_prompt_source": inspect.getsource(build_prompt),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def parse_decision(content: str) -> dict[str, Any]:
    """Parse a structured decision from bare or Markdown-fenced JSON.

    Some models wrap schema-constrained JSON in a ``json`` code fence.  Try the
    complete response first, then fenced blocks from last to first so a model's
    corrected final block takes precedence over an earlier draft.
    """
    candidates = [content.strip()]
    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(reversed(fenced))

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict) and parsed.get("decision") in {"ADD_CONSTRAINT", "ABSTAIN"}:
            return parsed
        last_error = ValueError("invalid decision")

    if last_error is not None:
        raise last_error
    raise ValueError("empty decision response")


def _normalized_span(span: str) -> str:
    return " ".join(span.strip().rstrip(".").split())


def _supports_gold_span(candidate_span: str, gold_span: str) -> bool:
    candidate = _normalized_span(candidate_span)
    gold = _normalized_span(gold_span)
    return candidate == gold or gold in candidate


def _semantically_equivalent(
    spec: ModelSpec,
    candidate: Constraint,
    gold: Constraint,
    timeout_ms: int = 5_000,
) -> bool:
    try:
        domain_spec = ModelSpec(spec.variables, (), spec.target, spec.metadata)
        domains = compile_spec(domain_spec)
        candidate_spec = ModelSpec(spec.variables, (candidate,), spec.target, spec.metadata)
        gold_spec = ModelSpec(spec.variables, (gold,), spec.target, spec.metadata)
        candidate_assertion = compile_spec(candidate_spec).assertions[-1]
        gold_assertion = compile_spec(gold_spec).assertions[-1]
    except UnsupportedExpression:
        return False

    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.add(*domains.assertions, z3.Xor(candidate_assertion, gold_assertion))
    return solver.check() == z3.unsat


def score(row: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    decision = output["decision"]
    label = row["label"]
    scored = {
        "is_abstain": decision == "ABSTAIN",
        "is_add": decision == "ADD_CONSTRAINT",
        "source_grounded": False,
        "semantic_repair": False,
        "functional_repair": False,
        "grounded_repair": False,
        "unsupported_repair": False,
        "correct_repair": False,
        # Backward-compatible alias. New analyses should use the explicit fields above.
        "valid_repair": False,
        "correct": False,
    }
    if decision == "ABSTAIN":
        scored["correct"] = label == "UNDERSPECIFIED"
        return scored
    span, expression = output.get("source_span"), output.get("constraint")
    if not isinstance(span, str) or not isinstance(expression, str):
        scored["unsupported_repair"] = True
        return scored
    scored["source_grounded"] = span in row["problem"]
    candidate = Constraint("candidate", expression, span, "EXPLICIT_TEXT")
    gate = validate_repair(row["problem"], ModelSpec.from_dict(row["spec"]), candidate)
    if gate.accepted and gate.determinacy and gate.determinacy.status == CheckStatus.DETERMINATE:
        scored["functional_repair"] = gate.determinacy.target_value == row["gold_target"]
    scored["valid_repair"] = scored["functional_repair"]

    gold_raw = row.get("missing_constraint")
    if label == "OMISSION" and isinstance(gold_raw, dict):
        gold = Constraint.from_dict(gold_raw)
        scored["semantic_repair"] = _semantically_equivalent(
            ModelSpec.from_dict(row["spec"]), candidate, gold
        )
        if gold.source_span:
            scored["grounded_repair"] = (
                scored["source_grounded"]
                and scored["semantic_repair"]
                and _supports_gold_span(span, gold.source_span)
            )
        scored["correct_repair"] = scored["functional_repair"] and scored["grounded_repair"]

    scored["unsupported_repair"] = scored["is_add"] and not scored["grounded_repair"]
    scored["correct"] = label == "OMISSION" and scored["correct_repair"]
    return scored
