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
    args = parser.parse_args()
    rows = []
    for pattern in args.patterns:
        for filename in glob.glob(pattern):
            rows.extend(map(json.loads, Path(filename).read_text().splitlines()))
    formalized = [row for row in rows if row.get("status") == "ok"]
    verified = [row for row in formalized if row.get("initial_verdict") in {"DETERMINATE", "AMBIGUOUS"}]
    rate = lambda field: sum(bool(row.get(field)) for row in verified) / len(verified) if verified else 0.0
    verdicts = Counter(row.get("initial_verdict") for row in formalized)
    ambiguous = [row for row in verified if row.get("initial_verdict") == "AMBIGUOUS"]
    report = {
        "selected": len(rows),
        "direct_cot_accuracy": sum(bool(row.get("direct_correct")) for row in rows) / len(rows) if rows else 0.0,
        "direct_cot_errors": sum(row.get("direct_status") == "error" for row in rows),
        "symcode_execution_rate": sum(row.get("symcode_status") == "ok" for row in rows) / len(rows) if rows else 0.0,
        "symcode_accuracy": sum(bool(row.get("symcode_correct")) for row in rows) / len(rows) if rows else 0.0,
        "symcode_errors": sum(row.get("symcode_status") == "error" for row in rows),
        "formalized": len(formalized),
        "formalized_and_verified": len(verified),
        "verification_coverage": len(verified) / len(rows) if rows else 0.0,
        "model_not_supported": sum(row.get("status") == "not_supported_by_model" for row in rows),
        "errors": sum(row.get("status") == "error" for row in rows),
        "initial_verdicts": dict(verdicts),
        "natural_underdetermined": len(ambiguous),
        "structured_accuracy_on_verified": rate("initial_correct"),
        "grounded_self_review_accuracy_on_verified": rate("review_correct"),
        "degro_accuracy_on_verified": rate("degro_correct"),
        "structured_accuracy_end_to_end": sum(bool(row.get("initial_correct")) for row in rows) / len(rows) if rows else 0.0,
        "grounded_self_review_accuracy_end_to_end": sum(bool(row.get("review_correct")) for row in rows) / len(rows) if rows else 0.0,
        "degro_accuracy_end_to_end": sum(bool(row.get("degro_correct")) for row in rows) / len(rows) if rows else 0.0,
        "degro_repairs_attempted": sum(row.get("degro_output") is not None for row in verified),
        "degro_repairs_accepted": sum(bool(row.get("degro_changed")) for row in verified),
        "degro_natural_cases_fixed": sum(not row.get("initial_correct") and row.get("degro_correct") for row in verified),
        "degro_cases_broken": sum(row.get("initial_correct") and not row.get("degro_correct") for row in verified),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
