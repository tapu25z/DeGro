#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import inspect
import json
import math
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from scripts.preannotate_natural_errors import ANNOTATION_SCHEMA, parse_proposal
except ModuleNotFoundError:
    from preannotate_natural_errors import ANNOTATION_SCHEMA, parse_proposal
from targetcheck.error_taxonomy import NaturalErrorAnnotation
from targetcheck.providers import OllamaCloudClient, load_api_keys


def numeric(value: Any) -> float | None:
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None


def compatible(result: dict, gold: list[float], tolerance: float = 1e-3) -> bool:
    values = result.get("values", [])
    if result.get("verdict") != "DETERMINATE" or not values or len(values) > len(gold):
        return False
    remaining = list(map(float, gold))
    for raw_value in values:
        value = numeric(raw_value)
        if value is None:
            return False
        match = next(
            (i for i, expected in enumerate(remaining) if math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance)),
            None,
        )
        if match is None:
            return False
        remaining.pop(match)
    return True


def selected_results(pattern: str) -> dict[tuple[str, str], dict]:
    selected = {}
    for filename in sorted(glob.glob(pattern)):
        for line in Path(filename).read_text().splitlines():
            row = json.loads(line)
            key = (row["id"], row["method"])
            if key not in selected or selected[key].get("status") == "error":
                selected[key] = row
    return selected


def adjudication_prompt(item: dict) -> str:
    return f"""You are the final AI adjudicator for a mathematical-formalization error study. Re-evaluate the case independently. The earlier semantic proposal and the verifier disagree; neither is authoritative.

Problem:
{item['problem']}

Released reference equations:
{json.dumps(item['gold_equations'], ensure_ascii=False)}

Released solution vector (contains every equation unknown, even when the question asks for only one):
{json.dumps(item['gold_solutions'])}

Generated formalization:
{json.dumps(item['formalization'], ensure_ascii=False, indent=2)}

Earlier semantic proposal:
{json.dumps(item['prior_annotation'], ensure_ascii=False, indent=2)}

Verifier evidence:
{json.dumps(item['verifier'], ensure_ascii=False, indent=2)}

Assign exactly one final primary label:
- CORRECT: faithfully represents the target-relevant task.
- MISSING_CONSTRAINT: a source-supported condition or required threshold/optimization condition whose omission can change the requested target is absent.
- WRONG_CONSTRAINT: an encoded relation mistranslates the source.
- EXTRA_CONSTRAINT: an unsupported assumption was added and changes the feasible task.
- WRONG_DOMAIN: a sort or bound changes feasible solutions or target determinacy.
- WRONG_TARGET: the target expression does not represent exactly what the question requests.
- COMPUTATIONAL_ERROR: the representation is faithful but downstream computation is wrong.
- OTHER: another semantic error.

Adjudication rules:
1. Judge semantic faithfulness, not answer compatibility alone.
2. A question asking for a minimum, maximum, threshold, or "how much ... must" is not fully represented by a loose inequality if many target values remain feasible.
3. A ratio encoded with division by a variable may need a source-supported nonzero/positive domain condition; account for solver division-by-zero semantics.
4. If the question asks for one quantity but the target list contains additional quantities, use WRONG_TARGET even when all values occur in the released solution vector.
5. Do not call an implicit physical nonnegativity condition EXTRA_CONSTRAINT unless it changes the target-relevant problem in an unsupported way.
6. Use WRONG_DOMAIN only when the domain choice actually changes feasible solutions or determinacy.
7. Set target_critical_underformalization=true exactly when the label is MISSING_CONSTRAINT.

Return exactly one JSON object with these keys and no Markdown:
{{"primary_label":"MISSING_CONSTRAINT","target_critical_underformalization":true,"evidence":"specific source/formalization comparison","notes":"brief adjudication rationale","confidence":"HIGH"}}"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Final GPT-OSS adjudication of ALG514 verifier/semantic disagreements.")
    parser.add_argument("--data", type=Path, default=Path("data/alg514/alg514.jsonl"))
    parser.add_argument("--annotations", type=Path, default=Path("data/natural_errors/gpt-oss_20b_alg514_all/gpt_oss_120b_annotations.jsonl"))
    parser.add_argument("--raw-pattern", default="results/raw/gpt-oss_20b_alg514_natural_all_low_shard*.jsonl")
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:120b")
    parser.add_argument("--think", choices=("none", "low", "medium", "high"), default="low")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    data = {row["unique_id"]: row for row in map(json.loads, args.data.read_text().splitlines())}
    annotations = {row["id"]: row for row in map(json.loads, args.annotations.read_text().splitlines())}
    results = selected_results(args.raw_pattern)
    structured = {uid: row for (uid, method), row in results.items() if method == "structured_solver"}
    disagreements = []
    for uid, annotation in annotations.items():
        result = structured[uid]
        numeric_ok = compatible(result, data[uid]["gold_solutions"])
        semantic_ok = annotation["primary_label"] == "CORRECT"
        if numeric_ok == semantic_ok:
            continue
        disagreements.append({
            **data[uid],
            "formalization": result.get("formalization"),
            "prior_annotation": {
                key: annotation[key]
                for key in ("primary_label", "target_critical_underformalization", "evidence", "notes", "confidence")
            },
            "verifier": {
                "initial_verdict": result.get("initial_verdict"),
                "final_verdict": result.get("verdict"),
                "values": result.get("values"),
                "alg514_compatible": numeric_ok,
            },
        })
    disagreements.sort(key=lambda row: row["unique_id"])
    disagreements = [row for index, row in enumerate(disagreements) if index % args.num_shards == args.shard_index]

    completed = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            row = json.loads(line)
            if row.get("status") == "ok":
                completed.add(row["id"])
    keys = load_api_keys(args.keys)
    client = OllamaCloudClient((keys[args.account_offset % len(keys)],), timeout_s=args.timeout)
    think: str | bool = False if args.think == "none" else args.think
    prompt_sha256 = hashlib.sha256(inspect.getsource(adjudication_prompt).encode()).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as stream:
        for index, item in enumerate(disagreements, 1):
            uid = item["unique_id"]
            if uid in completed:
                continue
            record = {"id": uid, "model": args.model, "think": args.think, "prompt_sha256": prompt_sha256}
            started = time.monotonic()
            try:
                response = client.chat(
                    args.model,
                    [{"role": "user", "content": adjudication_prompt(item)}],
                    format_schema=ANNOTATION_SCHEMA,
                    options={"temperature": 0.0, "num_predict": 1536},
                    think=think,
                )
                raw_content = response.get("message", {}).get("content", "")
                proposal, normalizations = parse_proposal(raw_content)
                NaturalErrorAnnotation.from_dict({"id": uid, **proposal})
                record.update(status="ok", proposal=proposal, normalizations=normalizations, raw_content=raw_content)
            except Exception as exc:
                record.update(status="error", error=f"{type(exc).__name__}: {str(exc)[:600]}")
            record["wall_seconds"] = round(time.monotonic() - started, 2)
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            print(f"[{index}/{len(disagreements)}] {uid} {record['status']}", flush=True)


if __name__ == "__main__":
    main()
