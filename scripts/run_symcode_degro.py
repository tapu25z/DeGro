#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from scripts.run_math500_six_methods import answer_correct, apply_grounded, parse_object, repair_prompt, resolve_source_span
from targetcheck.determinacy import CheckStatus, check_target_determinacy
from targetcheck.modelspec import Constraint, ModelSpec, Variable
from targetcheck.providers import OllamaCloudClient, load_api_keys


ADAPTER_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["SUPPORTED", "NOT_SUPPORTED"]},
        "variables": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "sort": {"type": "string", "enum": ["Int", "Real", "Bool"]},
            "lower": {"type": ["number", "null"]}, "upper": {"type": ["number", "null"]},
            "values": {"type": ["array", "null"], "items": {"type": "integer"},
        }, "required": ["name", "sort", "lower", "upper", "values"], "additionalProperties": False}},
        "constraints": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "expression": {"type": "string"},
            "source_span": {"type": "string"}, "code_span": {"type": "string"},
        }, "required": ["id", "expression", "source_span", "code_span"], "additionalProperties": False}},
        "target": {"type": "string"},
    },
    "required": ["status", "variables", "constraints", "target"],
    "additionalProperties": False,
}


def adapter_prompt(problem: str, code: str) -> str:
    return f"""Recover the declarative mathematical model actually encoded by this already-executed SymPy program.

Original problem (use only to quote exact source spans):
{problem}

Executed program:
```python
{code}
```

Return one JSON object matching the schema. Do not solve the problem. Do not constrain the target to the printed result or add a derived answer. Include only variables and target-relevant constraints materially used by the program before it chooses or prints a solution. Every constraint must cite both an exact contiguous source_span from the original problem and an exact contiguous code_span showing where the program encoded that fact. If the program cannot be represented using Int/Real/Bool variables and constraints with +, -, *, /, %, powers up to 4, comparisons, and/or, return NOT_SUPPORTED with empty arrays and target.

Use Python-style expressions with ==, !=, <, <=, >, >=, +, -, *, /, %, **, and, or. Never use calls, &&, ||, the symbol ∈, or prose. Never insert the program's final output as a constraint."""


def convert_adapter(raw: dict[str, Any], problem: str, code: str) -> tuple[ModelSpec | None, str]:
    if raw.get("status") != "SUPPORTED":
        return None, "adapter_not_supported"
    variables = tuple(Variable.from_dict(item) for item in raw.get("variables", []))
    constraints = []
    for item in raw.get("constraints", []):
        source = resolve_source_span(problem, item.get("source_span", ""))
        code_span = item.get("code_span")
        if source is None:
            return None, "source_span_not_found"
        if not isinstance(code_span, str) or code_span not in code:
            return None, "code_span_not_found"
        constraints.append(Constraint(item["id"], item["expression"], source, "EXPLICIT_TEXT"))
    try:
        return ModelSpec(variables, tuple(constraints), raw["target"]), "ok"
    except Exception as exc:
        return None, f"invalid_modelspec:{type(exc).__name__}"


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed = set()
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
            if row.get("status") != "error":
                completed.add(row["id"])
        except (json.JSONDecodeError, KeyError):
            pass
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int)
    parser.add_argument("--accounts-per-worker", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.data.read_text().splitlines()]
    rows = [row for index, row in enumerate(rows) if index % args.num_shards == args.shard_index]
    completed = load_completed(args.out)
    keys = load_api_keys(args.keys)
    offset = (args.account_offset if args.account_offset is not None else args.shard_index) % len(keys)
    rotated = keys[offset:] + keys[:offset]
    client = OllamaCloudClient(rotated[: min(args.accounts_per_worker, len(rotated))], timeout_s=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as stream:
        for index, row in enumerate(rows, 1):
            if row["id"] in completed:
                continue
            started = time.monotonic()
            record = {**row, "model": args.model, "think": args.think}
            raw_content = ""
            try:
                response = client.chat(args.model, [{"role": "user", "content": adapter_prompt(row["problem"], row["symcode_plus_code"])}], format_schema=ADAPTER_SCHEMA, options={"temperature": 0.0}, think=args.think)
                raw_content = str(response.get("message", {}).get("content", ""))
                raw = parse_object(raw_content)
                spec, adapter_reason = convert_adapter(raw, row["problem"], row["symcode_plus_code"])
                record.update(adapter=raw, adapter_reason=adapter_reason)
                if spec is None:
                    record.update(status="not_supported", verifier_coverage=False, degro_action="fallback", degro_answer=row["symcode_plus_answer"], degro_correct=row["symcode_plus_correct"])
                else:
                    initial = check_target_determinacy(spec)
                    record.update(initial_verdict=initial.status.value, initial_value=initial.target_value)
                    if initial.status == CheckStatus.AMBIGUOUS:
                        repair_response = client.chat(args.model, [{"role": "user", "content": repair_prompt(row["problem"], spec, determinacy=True, grounding=True)}], options={"temperature": 0.0}, think=args.think)
                        repair = parse_object(str(repair_response.get("message", {}).get("content", "")))
                        _, changed, reason, result = apply_grounded(row["problem"], spec, repair)
                        if changed and result.status == CheckStatus.DETERMINATE:
                            answer = result.target_value
                            record.update(status="ok", verifier_coverage=True, degro_action="repair", repair=repair, repair_reason=reason, final_verdict=result.status.value, degro_answer=answer, degro_correct=answer_correct(answer, row["gold_answer"]))
                        else:
                            record.update(status="ok", verifier_coverage=True, degro_action="abstain", repair=repair, repair_reason=reason, final_verdict=result.status.value, degro_answer=None, degro_correct=False)
                    elif initial.status == CheckStatus.DETERMINATE:
                        record.update(status="ok", verifier_coverage=True, degro_action="pass", degro_answer=row["symcode_plus_answer"], degro_correct=row["symcode_plus_correct"])
                    else:
                        record.update(status="not_supported", verifier_coverage=False, degro_action="fallback", degro_answer=row["symcode_plus_answer"], degro_correct=row["symcode_plus_correct"])
            except Exception as exc:
                record.update(status="error", error=f"{type(exc).__name__}: {str(exc)[:600]}", raw_content=raw_content[:3000])
            record["wall_seconds"] = round(time.monotonic() - started, 2)
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            print(f"[{index}/{len(rows)}] {row['id']} {record['status']} {record.get('degro_action')}", flush=True)


if __name__ == "__main__":
    main()
