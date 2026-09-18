#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

try:
    from scripts.run_olympiadbench_symcode import boxed, is_correct
except ModuleNotFoundError:  # Allow `python scripts/...py` from the repository root.
    from run_olympiadbench_symcode import boxed, is_correct


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--data", type=Path, default=Path("data/math500/test.jsonl"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-wrong", type=int, default=0, help="0 keeps every available execute-but-wrong case")
    parser.add_argument("--mode", choices=("balanced", "all"), default="balanced")
    parser.add_argument("--expected-results", type=int, default=0)
    args = parser.parse_args()

    problems = {row["unique_id"]: row for row in map(json.loads, args.data.read_text().splitlines())}
    best = {}
    source_files = []
    for pattern in args.patterns:
        for filename in sorted(glob.glob(pattern)):
            source_files.append(filename)
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                if row.get("method") != "symcode_plus" or row.get("status") == "error":
                    continue
                best[row["id"]] = row

    if args.expected_results and len(best) != args.expected_results:
        raise SystemExit(
            f"Expected {args.expected_results} completed SymCode+ results, found {len(best)}. "
            "Wait for the source run to finish, then rerun this command."
        )

    executable = []
    for uid, result in best.items():
        if not result.get("executed") or uid not in problems:
            continue
        attempts = result.get("attempts") or []
        successful = [attempt for attempt in attempts if attempt.get("status") == "ok" and attempt.get("code")]
        if not successful:
            continue
        problem = problems[uid]
        correct = is_correct(boxed(str(result.get("answer", ""))), [problem["answer"]])
        executable.append({
            "id": uid, "problem": problem["problem"], "gold_answer": problem["answer"],
            "subject": problem["subject"], "level": problem["level"],
            "symcode_plus_code": successful[-1]["code"],
            "symcode_plus_answer": result.get("answer"),
            "symcode_plus_correct": correct,
        })

    wrong = sorted((row for row in executable if not row["symcode_plus_correct"]), key=lambda row: row["id"])
    if args.max_wrong:
        wrong = wrong[: args.max_wrong]
    correct_pool = sorted((row for row in executable if row["symcode_plus_correct"]), key=lambda row: row["id"])
    controls, used = [], set()
    for error in wrong:
        priorities = (
            lambda row: row["subject"] == error["subject"] and row["level"] == error["level"],
            lambda row: row["subject"] == error["subject"],
            lambda row: True,
        )
        match = next((row for predicate in priorities for row in correct_pool if row["id"] not in used and predicate(row)), None)
        if match:
            used.add(match["id"])
            controls.append(match)
    if args.mode == "all":
        rows = [
            {**row, "cohort": "EXECUTED_CORRECT_CONTROL" if row["symcode_plus_correct"] else "EXECUTED_WRONG"}
            for row in executable
        ]
    else:
        rows = [{**row, "cohort": "EXECUTED_WRONG"} for row in wrong]
        rows += [{**row, "cohort": "EXECUTED_CORRECT_CONTROL"} for row in controls]
    rows.sort(key=lambda row: (row["cohort"], row["id"]))
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload)
    manifest = {
        "mode": args.mode, "source_results": len(best), "records": len(rows),
        "executed_wrong": sum(row["cohort"] == "EXECUTED_WRONG" for row in rows),
        "correct_controls": sum(row["cohort"] == "EXECUTED_CORRECT_CONTROL" for row in rows),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(), "source_files": source_files,
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
