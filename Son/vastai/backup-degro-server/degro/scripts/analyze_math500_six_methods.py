#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path

METHODS = ("symcode", "symcode_plus", "structured_solver", "grounded_self_review", "determinacy_only", "degro")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--tsv-out", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=500)
    args = parser.parse_args()
    chosen = {}
    for pattern in args.patterns:
        for filename in sorted(glob.glob(pattern)):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                key = (row["id"], row["method"])
                if key not in chosen or chosen[key].get("status") == "error":
                    chosen[key] = row
    report = {"expected_problems": args.expected, "unique_problems": len({key[0] for key in chosen}), "methods": {}}
    lines = ["method\trecords\taccuracy\texecution_or_verification_rate\terrors\tnot_supported"]
    for method in METHODS:
        rows = [row for (_, name), row in chosen.items() if name == method]
        correct = sum(bool(row.get("correct")) for row in rows)
        if method.startswith("symcode"):
            coverage = sum(bool(row.get("executed")) for row in rows)
        else:
            coverage = sum(row.get("verdict") in {"DETERMINATE", "AMBIGUOUS"} for row in rows)
        entry = {
            "records": len(rows), "correct": correct,
            "accuracy": correct / len(rows) if rows else 0.0,
            "raw_answer_accuracy": sum(bool(row.get("raw_correct", row.get("correct"))) for row in rows) / len(rows) if rows else 0.0,
            "execution_or_verification_rate": coverage / len(rows) if rows else 0.0,
            "errors": sum(row.get("status") == "error" for row in rows),
            "not_supported": sum(row.get("status") == "not_supported" for row in rows),
            "accepted_repairs": sum(bool(row.get("changed")) for row in rows),
            "grounded_valid_repairs": sum(bool(row.get("grounded_valid")) for row in rows),
            "direct_target_pins": sum(bool(row.get("direct_target_pin")) for row in rows),
            "verdicts": dict(Counter(row.get("verdict") for row in rows if row.get("verdict"))),
        }
        report["methods"][method] = entry
        lines.append(f"{method}\t{len(rows)}\t{entry['accuracy']:.6f}\t{entry['execution_or_verification_rate']:.6f}\t{entry['errors']}\t{entry['not_supported']}")
    report["complete"] = all(
        report["methods"][method]["records"] == args.expected
        and report["methods"][method]["errors"] == 0
        for method in METHODS
    )
    args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    args.tsv_out.write_text("\n".join(lines) + "\n")
    print(json.dumps(report, indent=2))
    if not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
