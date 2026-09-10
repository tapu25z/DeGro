#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import z3

try:
    from scripts.run_math500_natural import REPAIR_SCHEMA, parse_object
    from scripts.run_math500_six_methods import apply_grounded, response_metrics
except ModuleNotFoundError:
    from run_math500_natural import REPAIR_SCHEMA, parse_object
    from run_math500_six_methods import apply_grounded, response_metrics
from targetcheck.determinacy import CheckStatus, check_target_determinacy
from targetcheck.compiler_z3 import compile_spec, model_value
from targetcheck.modelspec import ModelSpec
from targetcheck.providers import OllamaCloudClient, load_api_keys


DRAW_FORMALIZATION_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["SUPPORTED", "NOT_SUPPORTED"]},
        "variables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}, "sort": {"type": "string", "enum": ["Int", "Real", "Bool"]},
                    "lower": {"type": ["number", "null"]}, "upper": {"type": ["number", "null"]},
                    "values": {"type": ["array", "null"], "items": {"type": "integer"}},
                },
                "required": ["name", "sort", "lower", "upper", "values"], "additionalProperties": False,
            },
        },
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"}, "expression": {"type": "string"},
                    "source_span": {"type": ["string", "null"]},
                    "provenance": {"type": "string", "enum": ["EXPLICIT_TEXT", "DOMAIN_SEMANTICS"]},
                },
                "required": ["id", "expression", "source_span", "provenance"], "additionalProperties": False,
            },
        },
        "targets": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2},
    },
    "required": ["status", "variables", "constraints", "targets"], "additionalProperties": False,
}


@dataclass(frozen=True)
class JointResult:
    status: CheckStatus
    values: tuple[Any, ...] = ()
    ambiguous_target: str | None = None
    witness_1: dict[str, Any] | None = None
    witness_2: dict[str, Any] | None = None
    reason: str | None = None


def formalization_prompt(problem: str) -> str:
    return f"""Translate this complete algebra word problem into a small Z3-compatible constraint model.
Problem:
{problem}

Return exactly one JSON object. Use SUPPORTED only when every requested numeric quantity can be represented with one or two Int/Real variables, arithmetic constraints, and scalar target expressions. `targets` must list all quantities requested by the question; preserve source order when possible. Encode every target-relevant fact, but do not solve the problem or insert final numeric answers as constraints.

Use only Python-style ==, !=, <, <=, >, >=, +, -, *, /, %, **, and/or. Never use function calls, including ToReal, or prose inside an expression; Z3 will coerce Int variables when multiplied by decimal constants. Every EXPLICIT_TEXT constraint must quote an exact contiguous source_span. DOMAIN_SEMANTICS is allowed only for conventional meanings such as nonnegative counts, positive speeds, or distinct requested quantities, and its source_span must be null.

Example:
{{"status":"SUPPORTED","variables":[{{"name":"x","sort":"Real","lower":null,"upper":null,"values":null}},{{"name":"y","sort":"Real","lower":null,"upper":null,"values":null}}],"constraints":[{{"id":"c1","expression":"x + y == 10","source_span":"Their sum is 10","provenance":"EXPLICIT_TEXT"}}],"targets":["x","y"]}}

For NOT_SUPPORTED return empty variables, constraints, and targets."""


def repair_prompt(problem: str, spec: ModelSpec, targets: list[str], result: JointResult) -> str:
    constraints = "\n".join(f"- {constraint.expression}" for constraint in spec.constraints)
    return f"""Audit this underdetermined algebra formalization.
Original problem:
{problem}

Current constraints:
{constraints}

Requested targets: {json.dumps(targets)}
Ambiguous target: {result.ambiguous_target}
Target-divergent witness 1: {json.dumps(result.witness_1, sort_keys=True)}
Target-divergent witness 2: {json.dumps(result.witness_2, sort_keys=True)}

Return exactly one JSON object. Add at most one missing source-supported constraint, or ABSTAIN. EXPLICIT_TEXT requires an exact contiguous source quote. DOMAIN_SEMANTICS is allowed only for a conventional mathematical domain rule and requires a null source_span. Never insert a derived final answer or a merely plausible assumption.

ADD example: {{"decision":"ADD_CONSTRAINT","source_span":"Their sum is 10","constraint":"x + y == 10","provenance":"EXPLICIT_TEXT"}}
ABSTAIN example: {{"decision":"ABSTAIN","source_span":null,"constraint":null,"provenance":null}}"""


def base_spec(raw: dict, target: str | None = None) -> ModelSpec:
    payload = {**raw, "target": target or raw["targets"][0]}
    payload.pop("targets", None)
    return ModelSpec.from_dict(payload)


def check_joint(raw_or_spec: dict | ModelSpec, targets: list[str] | None = None) -> JointResult:
    if isinstance(raw_or_spec, dict):
        targets = list(raw_or_spec.get("targets", []))
        if not targets:
            return JointResult(CheckStatus.NOT_SUPPORTED, reason="no requested targets")
        spec = base_spec(raw_or_spec, targets[0])
    else:
        spec = raw_or_spec
        targets = list(targets or [spec.target])
    if len(targets) == 2:
        # DRAW-1K and ALG514 evaluate solution lists without order.  For two
        # numeric targets, a multiset is uniquely determined iff its elementary
        # symmetric polynomials (sum and product) are uniquely determined.
        aggregates = [
            (f"({targets[0]}) + ({targets[1]})", "unordered target sum"),
            (f"({targets[0]}) * ({targets[1]})", "unordered target product"),
        ]
        for expression, label in aggregates:
            result = check_target_determinacy(ModelSpec(spec.variables, spec.constraints, expression, spec.metadata))
            if result.status == CheckStatus.AMBIGUOUS:
                return JointResult(result.status, ambiguous_target=label, witness_1=result.witness_1, witness_2=result.witness_2)
            if result.status != CheckStatus.DETERMINATE:
                return JointResult(result.status, reason=result.reason)
        compiled = compile_spec(spec)
        solver = z3.Solver()
        solver.add(*compiled.assertions)
        if solver.check() != z3.sat:
            return JointResult(CheckStatus.UNKNOWN, reason="failed to recover representative unordered solution")
        model = solver.model()
        values = tuple(
            model_value(model, compile_spec(ModelSpec(spec.variables, spec.constraints, target, spec.metadata)).target)
            for target in targets
        )
        return JointResult(CheckStatus.DETERMINATE, values)

    values = []
    for target in targets:
        target_spec = ModelSpec(spec.variables, spec.constraints, target, spec.metadata)
        result = check_target_determinacy(target_spec)
        if result.status == CheckStatus.AMBIGUOUS:
            return JointResult(result.status, tuple(values), target, result.witness_1, result.witness_2)
        if result.status != CheckStatus.DETERMINATE:
            return JointResult(result.status, tuple(values), reason=result.reason)
        values.append(result.target_value)
    return JointResult(CheckStatus.DETERMINATE, tuple(values))


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None


def answers_match(values: tuple[Any, ...], gold: list[float], tolerance: float = 1e-5) -> bool:
    predicted = [numeric(value) for value in values]
    if len(predicted) != len(gold) or any(value is None for value in predicted):
        return False
    remaining = list(map(float, gold))
    for value in predicted:
        match = next((i for i, expected in enumerate(remaining) if math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance)), None)
        if match is None:
            return False
        remaining.pop(match)
    return not remaining


def existing_rows(path: Path) -> dict[tuple[str, str], dict]:
    chosen = {}
    if not path.exists():
        return chosen
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
            key = (row["id"], row["method"])
            if key not in chosen or chosen[key].get("status") == "error":
                chosen[key] = row
        except (json.JSONDecodeError, KeyError):
            pass
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DRAW-1K joint-target natural-error study.")
    parser.add_argument("--data", type=Path, default=Path("data/draw1k/draw1k.jsonl"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--split", choices=("train", "dev", "test", "all"), default="test")
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int)
    parser.add_argument("--repair-rounds", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.data.read_text().splitlines()]
    if args.split != "all":
        rows = [row for row in rows if row["split"] == args.split]
    if args.limit is not None:
        rows = rows[: args.limit]
    rows = [row for index, row in enumerate(rows) if index % args.num_shards == args.shard_index]
    chosen = existing_rows(args.out)
    keys = load_api_keys(args.keys)
    offset = (args.account_offset if args.account_offset is not None else args.shard_index) % len(keys)
    client = OllamaCloudClient((keys[offset],), timeout_s=args.timeout)
    prompt_hash = hashlib.sha256((inspect.getsource(formalization_prompt) + inspect.getsource(repair_prompt)).encode()).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def write(stream, item: dict, method: str, **fields: Any) -> None:
        record = {"id": item["unique_id"], "source_index": item["source_index"], "split": item["split"], "model": args.model, "think": args.think, "prompt_sha256": prompt_hash, "method": method, **fields}
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        chosen[(item["unique_id"], method)] = record

    with args.out.open("a") as stream:
        for index, item in enumerate(rows, 1):
            uid = item["unique_id"]
            pending = [method for method in ("structured_solver", "degro") if (uid, method) not in chosen or chosen[(uid, method)].get("status") == "error"]
            if not pending:
                continue
            raw = None
            cached = chosen.get((uid, "structured_solver"))
            if cached and cached.get("status") == "ok":
                raw = cached.get("formalization")
            try:
                if raw is None:
                    response = client.chat(args.model, [{"role": "user", "content": formalization_prompt(item["problem"])}], format_schema=DRAW_FORMALIZATION_SCHEMA, options={"temperature": 0.0, "num_predict": 2048}, think=args.think)
                    raw = parse_object(str(response.get("message", {}).get("content", "")))
                    metrics = response_metrics(response)
                else:
                    metrics = cached.get("formalization_metrics", {})
                if raw.get("status") != "SUPPORTED" or not raw.get("targets"):
                    for method in pending:
                        write(stream, item, method, status="not_supported", correct=False, formalization=raw, formalization_metrics=metrics)
                    continue
                initial = check_joint(raw)
                initial_fields = {"formalization": raw, "formalization_metrics": metrics, "initial_verdict": initial.status.value, "initial_values": initial.values}
                if "structured_solver" in pending:
                    write(stream, item, "structured_solver", status="ok", verdict=initial.status.value, values=initial.values, correct=initial.status == CheckStatus.DETERMINATE and answers_match(initial.values, item["gold_solutions"]), **initial_fields)
                if "degro" in pending:
                    current_spec = base_spec(raw)
                    current = initial
                    repairs = []
                    for round_index in range(args.repair_rounds):
                        if current.status != CheckStatus.AMBIGUOUS:
                            break
                        response = client.chat(args.model, [{"role": "user", "content": repair_prompt(item["problem"], current_spec, raw["targets"], current)}], format_schema=REPAIR_SCHEMA, options={"temperature": 0.0, "num_predict": 2048}, think=args.think)
                        proposal = parse_object(str(response.get("message", {}).get("content", "")))
                        repaired, changed, reason, _ = apply_grounded(item["problem"], ModelSpec(current_spec.variables, current_spec.constraints, current.ambiguous_target or current_spec.target, current_spec.metadata), proposal)
                        repairs.append({"round": round_index + 1, "proposal": proposal, "changed": changed, "reason": reason, "metrics": response_metrics(response)})
                        if not changed:
                            break
                        current_spec = repaired
                        current = check_joint(current_spec, raw["targets"])
                    write(stream, item, "degro", status="ok", triggered=initial.status == CheckStatus.AMBIGUOUS, changed=any(row["changed"] for row in repairs), repairs=repairs, verdict=current.status.value, values=current.values, correct=current.status == CheckStatus.DETERMINATE and answers_match(current.values, item["gold_solutions"]), **initial_fields)
            except Exception as exc:
                for method in pending:
                    if (uid, method) not in chosen or chosen[(uid, method)].get("status") == "error":
                        write(stream, item, method, status="error", error=f"{type(exc).__name__}: {str(exc)[:600]}", formalization=raw, correct=False)
            print(f"[{index}/{len(rows)}] {uid} pending={pending}", flush=True)


if __name__ == "__main__":
    main()
