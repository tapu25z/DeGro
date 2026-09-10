#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("results/raw/gpt_oss_20b_pilot.jsonl"))
    args = parser.parse_args()
    groups = defaultdict(list)
    for line in args.path.read_text().splitlines():
        row = json.loads(line)
        if row.get("status") == "ok":
            groups[row["method"]].append(row)
    print("method\tn\tRSR\tSemantic\tFunctional\tGrounded\tCAR\tFDA\tORR\tUnsupported\terrors_excluded")
    for method in sorted(groups):
        rows = groups[method]
        omissions = [r for r in rows if r["label"] == "OMISSION"]
        underspecified = [r for r in rows if r["label"] == "UNDERSPECIFIED"]
        rate = lambda values: sum(values) / len(values) if values else float("nan")
        rsr = rate([r["score"].get("correct_repair", r["score"]["valid_repair"]) for r in omissions])
        semantic = rate([r["score"].get("semantic_repair", False) for r in omissions])
        functional = rate([r["score"].get("functional_repair", r["score"]["valid_repair"]) for r in omissions])
        grounded = rate([r["score"].get("grounded_repair", False) for r in omissions])
        car = rate([r["score"]["is_abstain"] for r in underspecified])
        fda = rate([r["score"]["correct"] for r in rows])
        orr = rate([r["score"]["is_add"] for r in underspecified])
        additions = [r for r in rows if r["score"]["is_add"]]
        unsupported = rate([r["score"].get("unsupported_repair", True) for r in additions])
        print(
            f"{method}\t{len(rows)}\t{rsr:.3f}\t{semantic:.3f}\t{functional:.3f}\t"
            f"{grounded:.3f}\t{car:.3f}\t{fda:.3f}\t{orr:.3f}\t{unsupported:.3f}\t0"
        )


if __name__ == "__main__":
    main()
