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
    args = parser.parse_args()
    best = {}
    for pattern in args.patterns:
        for filename in glob.glob(pattern):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                if row["id"] not in best or best[row["id"]].get("status") == "error":
                    best[row["id"]] = row
    all_rows = list(best.values())
    errors = [row for row in all_rows if row.get("status") == "error"]
    rows = [row for row in all_rows if row.get("status") != "error"]
    wrong = [row for row in rows if row["cohort"] == "EXECUTED_WRONG"]
    controls = [row for row in rows if row["cohort"] == "EXECUTED_CORRECT_CONTROL"]
    covered = [row for row in rows if row.get("verifier_coverage")]
    baseline_correct = sum(bool(row.get("symcode_plus_correct")) for row in rows)
    degro_correct = sum(bool(row.get("degro_correct")) for row in rows)
    report = {
        "records": len(rows), "errors": len(errors),
        "symcode_plus_correct": baseline_correct,
        "symcode_plus_accuracy": baseline_correct / len(rows) if rows else 0.0,
        "symcode_plus_degro_correct": degro_correct,
        "symcode_plus_degro_accuracy": degro_correct / len(rows) if rows else 0.0,
        "accuracy_delta_pp": 100.0 * (degro_correct - baseline_correct) / len(rows) if rows else 0.0,
        "verifier_coverage": sum(bool(row.get("verifier_coverage")) for row in rows) / len(rows) if rows else 0.0,
        "covered_records": len(covered),
        "covered_symcode_plus_accuracy": sum(bool(row.get("symcode_plus_correct")) for row in covered) / len(covered) if covered else 0.0,
        "covered_symcode_plus_degro_accuracy": sum(bool(row.get("degro_correct")) for row in covered) / len(covered) if covered else 0.0,
        "verdicts": dict(Counter(row.get("initial_verdict") for row in rows if row.get("initial_verdict"))),
        "actions": dict(Counter(row.get("degro_action") for row in rows if row.get("degro_action"))),
        "executed_wrong": len(wrong),
        "wrong_cases_repaired": sum(bool(row.get("degro_correct")) for row in wrong),
        "repair_rate_on_executed_wrong": sum(bool(row.get("degro_correct")) for row in wrong) / len(wrong) if wrong else 0.0,
        "correct_controls": len(controls),
        "correct_controls_preserved": sum(bool(row.get("degro_correct")) for row in controls),
        "preservation_rate": sum(bool(row.get("degro_correct")) for row in controls) / len(controls) if controls else 0.0,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
