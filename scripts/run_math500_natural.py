#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

from targetcheck.determinacy import CheckStatus, check_target_determinacy
from targetcheck.grounding import validate_repair
from targetcheck.modelspec import Constraint, ModelSpec
from targetcheck.providers import OllamaCloudClient, load_api_keys
from targetcheck.symcode import execute_symcode


FORMALIZATION_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["SUPPORTED", "NOT_SUPPORTED"]},
        "variables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sort": {"type": "string", "enum": ["Int", "Real", "Bool"]},
                    "lower": {"type": ["number", "null"]},
                    "upper": {"type": ["number", "null"]},
                    "values": {"type": ["array", "null"], "items": {"type": "integer"}},
                },
                "required": ["name", "sort", "lower", "upper", "values"],
                "additionalProperties": False,
            },
        },
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "expression": {"type": "string"},
                    "source_span": {"type": ["string", "null"]},
                    "provenance": {"type": "string", "enum": ["EXPLICIT_TEXT", "DOMAIN_SEMANTICS"]},
                },
                "required": ["id", "expression", "source_span", "provenance"],
                "additionalProperties": False,
            },
        },
        "target": {"type": "string"},
    },
    "required": ["status", "variables", "constraints", "target"],
    "additionalProperties": False,
}

REPAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["ADD_CONSTRAINT", "ABSTAIN"]},
        "source_span": {"type": ["string", "null"]},
        "constraint": {"type": ["string", "null"]},
        "provenance": {"type": ["string", "null"], "enum": ["EXPLICIT_TEXT", "DOMAIN_SEMANTICS", None]},
    },
    "required": ["decision", "source_span", "constraint", "provenance"],
    "additionalProperties": False,
}

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"final_answer": {"type": "string"}},
    "required": ["final_answer"],
    "additionalProperties": False,
}

SYMCODE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["SUPPORTED", "NOT_SUPPORTED"]},
        "code": {"type": "string"},
    },
    "required": ["status", "code"],
    "additionalProperties": False,
}

PILOT_IDS = (
    "test/prealgebra/1622.json",
    "test/algebra/1837.json",
    "test/algebra/2427.json",
    "test/prealgebra/1840.json",
    "test/number_theory/627.json",
    "test/algebra/24.json",
    "test/algebra/2214.json",
    "test/prealgebra/1388.json",
    "test/prealgebra/572.json",
    "test/algebra/769.json",
    "test/algebra/722.json",
    "test/prealgebra/1247.json",
    "test/prealgebra/1233.json",
    "test/algebra/1004.json",
    "test/prealgebra/192.json",
    "test/algebra/1035.json",
    "test/prealgebra/307.json",
    "test/prealgebra/1761.json",
    "test/algebra/2593.json",
    "test/prealgebra/505.json",
)


def parse_object(content: str) -> dict[str, Any]:
    candidates = [content.strip()]
    candidates.extend(reversed(re.findall(r"```(?:json)?\s*(.*?)\s*```", content, re.I | re.S)))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("response does not contain a JSON object")


def numeric_answer(text: str) -> Fraction | None:
    value = text.strip().replace("$", "").replace(",", "").replace(" ", "")
    boxed = re.fullmatch(r"\\boxed\{(.+)\}", value)
    if boxed:
        value = boxed.group(1)
    value = value.replace("\\%", "").replace("%", "")
    match = re.fullmatch(r"(-?)\\(?:d?frac)\{(-?\d+)\}\{(\d+)\}", value)
    if match:
        sign, numerator, denominator = match.groups()
        result = Fraction(int(numerator), int(denominator))
        return -result if sign else result
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return Fraction(value)
    if re.fullmatch(r"-?\d+/\d+", value):
        return Fraction(value)
    return None


def target_fraction(value: Any) -> Fraction | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None


def formalization_prompt(problem: str) -> str:
    return f"""Translate this problem into a small Z3-compatible constraint model.
Problem:
{problem}

Return one JSON object matching the schema. Use SUPPORTED only when the requested scalar numeric answer can be represented with Int/Real/Bool variables and constraints using +, -, *, /, %, integer powers up to 4, comparisons, and/or. Otherwise return NOT_SUPPORTED with empty arrays and an empty target.

For SUPPORTED: encode every target-relevant fact, but do not solve the problem and do not insert the final answer as a constraint. Use Python-style == for equality. Each EXPLICIT_TEXT constraint must quote an exact contiguous source_span from the problem. DOMAIN_SEMANTICS is allowed only for conventional meanings such as positive counts or distinct objects.

Use exactly this structure and key names; never use keys named type, text, lhs, or rhs:
{{"status":"SUPPORTED","variables":[{{"name":"x","sort":"Real","lower":null,"upper":null,"values":null}}],"constraints":[{{"id":"c1","expression":"x == 3","source_span":"x is 3","provenance":"EXPLICIT_TEXT"}}],"target":"x"}}
For NOT_SUPPORTED use:
{{"status":"NOT_SUPPORTED","variables":[],"constraints":[],"target":""}}"""


def direct_prompt(problem: str) -> str:
    return f"""Solve the following mathematics problem. Return only one JSON object with a final_answer string containing the concise scalar answer and no explanation.
Problem:
{problem}

Output example: {{"final_answer":"3/2"}}"""


def symcode_prompt(problem: str) -> str:
    return f"""Solve this mathematics problem using executable SymPy code.
Problem:
{problem}

Return one JSON object with status and code. The code must not import anything and must assign the single scalar answer to a variable named result. Available names are symbols, Symbol, Eq, solve, solveset, simplify, expand, factor, Rational, Integer, sqrt, factorial, binomial, gcd, lcm, ceiling, floor, Abs, log, sin, cos, tan, summation, product, diff, integrate, Mod, Min, Max, pi, E, and oo. Use only assignments and expressions; no loops, comprehensions, functions, attributes, file access, or network access. If this language cannot express the solution, return {{"status":"NOT_SUPPORTED","code":""}}.

Example: {{"status":"SUPPORTED","code":"x = symbols('x')\nresult = solve(Eq(x/2 + x/3, 5), x)[0]"}}"""


def repair_prompt(problem: str, spec: ModelSpec, *, determinacy_signal: bool) -> str:
    constraints = "\n".join(f"- {constraint.expression}" for constraint in spec.constraints)
    signal = "\nSolver verdict: the target is not uniquely determined by the current constraints.\n" if determinacy_signal else ""
    return f"""Audit this mathematical formalization.
Original problem:
{problem}

Current constraints:
{constraints}

Target: {spec.target}
{signal}
Return exactly one JSON object. Add at most one missing constraint, or abstain.
For an explicit fact, provenance must be EXPLICIT_TEXT and source_span must be an exact contiguous substring of the original problem. For a conventional mathematical domain rule directly licensed by the described objects (for example, counts are nonnegative integers, a nonzero group size is positive, or a reassigned count cannot exceed the available count), provenance may be DOMAIN_SEMANTICS and source_span must be null. Do not add a derived final answer or an assumption that is merely plausible.

ADD example:
{{"decision":"ADD_CONSTRAINT","source_span":null,"constraint":"x > 0","provenance":"DOMAIN_SEMANTICS"}}
ABSTAIN example:
{{"decision":"ABSTAIN","source_span":null,"constraint":null,"provenance":null}}"""


def apply_repair(problem: str, spec: ModelSpec, output: dict[str, Any]) -> tuple[ModelSpec, bool, str]:
    if output.get("decision") != "ADD_CONSTRAINT":
        return spec, False, "abstain"
    span, expression = output.get("source_span"), output.get("constraint")
    if not isinstance(expression, str):
        return spec, False, "malformed"
    provenance = output.get("provenance")
    if provenance not in {"EXPLICIT_TEXT", "DOMAIN_SEMANTICS"}:
        return spec, False, "missing provenance"
    if provenance == "EXPLICIT_TEXT" and not isinstance(span, str):
        return spec, False, "missing source span"
    if provenance == "DOMAIN_SEMANTICS" and span is not None:
        return spec, False, "domain semantic repair must not cite a source span"
    candidate = Constraint("repair", expression, span, provenance)
    gate = validate_repair(problem, spec, candidate)
    if not gate.accepted or gate.repaired_spec is None:
        return spec, False, gate.reason
    return gate.repaired_spec, True, "accepted"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/math500/test.jsonl"))
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--selection", choices=("curated", "broad"), default="curated")
    parser.add_argument("--only-id", action="append", default=[])
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int, default=0)
    parser.add_argument("--accounts-per-worker", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    candidates_by_id = {}
    broad_candidates = []
    for row in map(json.loads, args.data.read_text().splitlines()):
        gold = numeric_answer(row["answer"])
        if gold is not None and row["subject"] in {"Prealgebra", "Algebra", "Intermediate Algebra", "Number Theory", "Counting & Probability"}:
            broad_candidates.append((row, gold))
        if gold is not None and row["unique_id"] in PILOT_IDS:
            candidates_by_id[row["unique_id"]] = (row, gold)
    if args.selection == "broad":
        candidates = broad_candidates[: args.limit]
    else:
        candidates = [candidates_by_id[unique_id] for unique_id in PILOT_IDS if unique_id in candidates_by_id][: args.limit]
    if args.only_id:
        selected_ids = set(args.only_id)
        candidates = [item for item in candidates if item[0]["unique_id"] in selected_ids]
    candidates = [item for index, item in enumerate(candidates) if index % args.num_shards == args.shard_index]

    completed: set[str] = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            try:
                completed.add(json.loads(line)["unique_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    candidates = [item for item in candidates if item[0]["unique_id"] not in completed]

    keys = load_api_keys(args.keys)
    offset = args.account_offset % len(keys)
    rotated = keys[offset:] + keys[:offset]
    worker_keys = rotated[: max(1, min(args.accounts_per_worker, len(rotated)))]
    client = OllamaCloudClient(worker_keys, timeout_s=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as stream:
        for index, (row, gold) in enumerate(candidates, 1):
            started = time.monotonic()
            record: dict[str, Any] = {
                "unique_id": row["unique_id"], "subject": row["subject"], "level": row["level"],
                "problem": row["problem"], "gold_answer": row["answer"], "gold_numeric": str(gold),
                "model": args.model, "think": args.think, "temperature": 0.0,
            }
            try:
                response = client.chat(args.model, [{"role": "user", "content": direct_prompt(row["problem"])}], format_schema=ANSWER_SCHEMA, options={"temperature": 0.0}, think=args.think)
                direct = parse_object(response.get("message", {}).get("content", ""))
                record.update({"direct_status": "ok", "direct_answer": direct.get("final_answer"), "direct_correct": numeric_answer(str(direct.get("final_answer", ""))) == gold})
            except Exception as exc:
                record.update({"direct_status": "error", "direct_error": f"{type(exc).__name__}: {str(exc)[:300]}", "direct_correct": False})
            try:
                response = client.chat(args.model, [{"role": "user", "content": symcode_prompt(row["problem"])}], format_schema=SYMCODE_SCHEMA, options={"temperature": 0.0}, think=args.think)
                symcode = parse_object(response.get("message", {}).get("content", ""))
                record["symcode_raw"] = symcode
                if symcode.get("status") != "SUPPORTED":
                    record.update({"symcode_status": "not_supported", "symcode_correct": False})
                else:
                    symcode_value = execute_symcode(symcode.get("code", ""))
                    record.update({"symcode_status": "ok", "symcode_value": str(symcode_value), "symcode_correct": target_fraction(symcode_value) == gold})
            except Exception as exc:
                record.update({"symcode_status": "error", "symcode_error": f"{type(exc).__name__}: {str(exc)[:300]}", "symcode_correct": False})
            try:
                response = client.chat(args.model, [{"role": "user", "content": formalization_prompt(row["problem"])}], format_schema=FORMALIZATION_SCHEMA, options={"temperature": 0.0}, think=args.think)
                content = response.get("message", {}).get("content", "")
                raw = parse_object(content)
                record["formalization_raw"] = raw
                if raw.get("status") != "SUPPORTED":
                    record["status"] = "not_supported_by_model"
                else:
                    spec = ModelSpec.from_dict(raw)
                    initial = check_target_determinacy(spec)
                    record["status"] = "ok"
                    record["initial_verdict"] = initial.status.value
                    record["initial_value"] = initial.target_value
                    record["initial_correct"] = target_fraction(initial.target_value) == gold
                    audit_row = {"problem": row["problem"], "spec": raw, "pair_id": row["unique_id"]}

                    review_response = client.chat(args.model, [{"role": "user", "content": repair_prompt(row["problem"], spec, determinacy_signal=False)}], format_schema=REPAIR_SCHEMA, options={"temperature": 0.0}, think=args.think)
                    review_output = parse_object(review_response.get("message", {}).get("content", ""))
                    review_spec, review_changed, review_reason = apply_repair(row["problem"], spec, review_output)
                    review_result = check_target_determinacy(review_spec)
                    record.update({"review_output": review_output, "review_changed": review_changed, "review_reason": review_reason, "review_verdict": review_result.status.value, "review_value": review_result.target_value, "review_correct": target_fraction(review_result.target_value) == gold})

                    if initial.status == CheckStatus.AMBIGUOUS:
                        degro_response = client.chat(args.model, [{"role": "user", "content": repair_prompt(row["problem"], spec, determinacy_signal=True)}], format_schema=REPAIR_SCHEMA, options={"temperature": 0.0}, think=args.think)
                        degro_output = parse_object(degro_response.get("message", {}).get("content", ""))
                        degro_spec, degro_changed, degro_reason = apply_repair(row["problem"], spec, degro_output)
                    else:
                        degro_output, degro_spec, degro_changed, degro_reason = None, spec, False, "not_triggered"
                    degro_result = check_target_determinacy(degro_spec)
                    record.update({"degro_output": degro_output, "degro_changed": degro_changed, "degro_reason": degro_reason, "degro_verdict": degro_result.status.value, "degro_value": degro_result.target_value, "degro_correct": target_fraction(degro_result.target_value) == gold})
            except Exception as exc:
                record.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]})
            record["wall_seconds"] = round(time.monotonic() - started, 3)
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            print(f"[{index}/{len(candidates)}] {row['unique_id']} {record['status']}", flush=True)


if __name__ == "__main__":
    main()
