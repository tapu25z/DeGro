#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=200)
    args = parser.parse_args()
    chosen = {}
    for pattern in args.patterns:
        for filename in sorted(glob.glob(pattern)):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                key = (row["id"], row["method"])
                if key not in chosen or chosen[key].get("status") == "error":
                    chosen[key] = row
    report = {"expected": args.expected, "unique_problems": len({uid for uid, _ in chosen}), "methods": {}}
    for method in ("structured_solver", "degro"):
        rows = [row for (_, name), row in chosen.items() if name == method]
        conclusive = [row for row in rows if row.get("initial_verdict") in {"DETERMINATE", "AMBIGUOUS"}]
        report["methods"][method] = {
            "records": len(rows),
            "errors": sum(row.get("status") == "error" for row in rows),
            "not_supported": sum(row.get("status") == "not_supported" for row in rows),
            "joint_verifier_coverage": len(conclusive) / len(rows) if rows else 0.0,
            "accuracy": sum(bool(row.get("correct")) for row in rows) / len(rows) if rows else 0.0,
            "accuracy_on_covered": sum(bool(row.get("correct")) for row in conclusive) / len(conclusive) if conclusive else 0.0,
            "initial_verdicts": dict(Counter(row.get("initial_verdict") for row in rows if row.get("initial_verdict"))),
            "triggered": sum(bool(row.get("triggered")) for row in rows),
            "accepted_repairs": sum(bool(row.get("changed")) for row in rows),
        }
    report["complete"] = all(report["methods"][method]["records"] == args.expected and report["methods"][method]["errors"] == 0 for method in report["methods"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
