#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from targetcheck.pilot import METHODS, prompt_hash


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("results/gpt_oss_20b_pilot_complete.jsonl"))
    parser.add_argument("--data", type=Path, default=Path("data/paired/mira_pilot_80.jsonl"))
    parser.add_argument("--input-glob", action="append", dest="input_globs")
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.data.read_text().splitlines()]
    expected = {(row["pair_id"], row["label"], method) for row in cases for method in args.methods}
    patterns = args.input_globs or [
        "results/raw/gpt_oss_20b_pilot_shard*.jsonl",
        "results/raw/gpt_oss_20b_s*.jsonl",
    ]
    files = []
    for pattern in patterns:
        files.extend(sorted(glob.glob(pattern)))
    best = {}
    for filename in files:
        for line in Path(filename).read_text().splitlines():
            row = json.loads(line)
            row["prompt_hash"] = prompt_hash()
            key = (row["pair_id"], row["label"], row["method"])
            if key not in expected:
                continue
            if row.get("status") == "ok":
                best[key] = row
            elif key not in best:
                best[key] = row
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(best.values(), key=lambda row: (row["pair_id"], row["label"], row["method"]))
    args.out.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in ordered))
    ok = sum(row.get("status") == "ok" for row in ordered)
    complete = ok == len(expected)
    print(json.dumps({
        "records": len(ordered),
        "expected": len(expected),
        "ok": ok,
        "errors": len(ordered) - ok,
        "missing": len(expected - set(best)),
        "complete": complete,
    }))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
