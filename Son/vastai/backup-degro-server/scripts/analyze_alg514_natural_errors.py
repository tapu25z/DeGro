#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any


def numeric(value: Any) -> float | None:
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None


def matches_gold_subset(result: dict, gold: list[float], tolerance: float) -> bool:
    """ALG514 stores every equation unknown, while questions may request a subset."""
    values = result.get("values", [])
    if result.get("verdict") != "DETERMINATE" or not values or len(values) > len(gold):
        return False
    remaining = list(map(float, gold))
    for raw_value in values:
        value = numeric(raw_value)
        if value is None:
            return False
        match = next(
            (
                index
                for index, expected in enumerate(remaining)
                if math.isclose(value, expected, rel_tol=tolerance, abs_tol=tolerance)
            ),
            None,
        )
        if match is None:
            return False
        remaining.pop(match)
    return True


def selected_results(pattern: str) -> dict[tuple[str, str], dict]:
    selected: dict[tuple[str, str], dict] = {}
    for filename in sorted(glob.glob(pattern)):
        for line in Path(filename).read_text().splitlines():
            row = json.loads(line)
            key = (row["id"], row["method"])
            if key not in selected or selected[key].get("status") == "error":
                selected[key] = row
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the ALG514 natural-error cohort.")
    parser.add_argument("--data", type=Path, default=Path("data/alg514/alg514.jsonl"))
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("data/natural_errors/gpt-oss_20b_alg514_all/gpt_oss_120b_annotations.jsonl"),
    )
    parser.add_argument(
        "--raw-pattern",
        default="results/raw/gpt-oss_20b_alg514_natural_all_low_shard*.jsonl",
    )
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--out", type=Path, default=Path("results/gpt_oss_120b_alg514_natural_error_summary.json"))
    args = parser.parse_args()

    data = {row["unique_id"]: row for row in map(json.loads, args.data.read_text().splitlines())}
    annotations = list(map(json.loads, args.annotations.read_text().splitlines()))
    annotation_by_id = {row["id"]: row for row in annotations}
    results = selected_results(args.raw_pattern)
    human_verified = bool(annotations) and all(row.get("review_status") == "VERIFIED_ACCEPT" for row in annotations)

    methods = {}
    for method in ("structured_solver", "degro"):
        rows = [row for (uid, name), row in results.items() if name == method]
        compatible = sum(matches_gold_subset(row, data[row["id"]]["gold_solutions"], args.tolerance) for row in rows)
        methods[method] = {
            "records": len(rows),
            "legacy_exact_cardinality_correct": sum(bool(row.get("correct")) for row in rows),
            "alg514_compatible_correct": compatible,
            "alg514_compatible_accuracy": compatible / len(data),
            "ambiguous_triggers": sum(row.get("initial_verdict") == "AMBIGUOUS" for row in rows),
            "accepted_repairs": sum(bool(row.get("changed")) for row in rows),
            "resolved_repairs": sum(
                row.get("initial_verdict") == "AMBIGUOUS" and row.get("verdict") == "DETERMINATE"
                for row in rows
            ),
        }

    labels = collections.Counter(row["primary_label"] for row in annotations)
    confidence = collections.Counter(row["confidence"] for row in annotations)
    fold_rows = {}
    for fold in range(5):
        rows = [row for row in annotations if data[row["id"]]["fold"] == fold]
        counts = collections.Counter(row["primary_label"] for row in rows)
        errors = len(rows) - counts.get("CORRECT", 0)
        fold_rows[str(fold)] = {
            "cohort_records": len(rows),
            "semantic_errors": errors,
            "semantic_error_rate": errors / len(rows),
            "labels": dict(sorted(counts.items())),
        }

    structured = {uid: row for (uid, method), row in results.items() if method == "structured_solver"}
    excluded = sorted(set(data) - set(annotation_by_id))
    output = {
        "study": "ALG514 natural-error study",
        "status": "human verified" if human_verified else "AI proposals pending human verification",
        "dataset_records": len(data),
        "frozen_cohort_records": len(annotations),
        "excluded_records": len(excluded),
        "excluded_ids": excluded,
        "annotation_model": "gpt-oss:120b",
        "human_verified": human_verified,
        "human_reviewers": max((int(row.get("human_reviewers", 0)) for row in annotations), default=0),
        "labels": dict(sorted(labels.items())),
        "semantic_correct_rate_on_cohort": labels.get("CORRECT", 0) / len(annotations),
        "semantic_error_rate_on_cohort": (len(annotations) - labels.get("CORRECT", 0)) / len(annotations),
        "target_critical_underformalization_rate": labels.get("MISSING_CONSTRAINT", 0) / len(annotations),
        "confidence": dict(sorted(confidence.items())),
        "methods": methods,
        "folds": fold_rows,
        "metric_note": (
            "ALG514-compatible scoring treats predicted target values as a multiset subset of the "
            "released all-unknown solution vector and uses tolerance 1e-3 for rounded gold values."
        ),
        "disagreement": {
            "semantic_correct_but_alg514_compatible_wrong": sum(
                annotation_by_id[uid]["primary_label"] == "CORRECT"
                and not matches_gold_subset(row, data[uid]["gold_solutions"], args.tolerance)
                for uid, row in structured.items()
                if uid in annotation_by_id
            ),
            "semantic_error_but_alg514_compatible_correct": sum(
                annotation_by_id[uid]["primary_label"] != "CORRECT"
                and matches_gold_subset(row, data[uid]["gold_solutions"], args.tolerance)
                for uid, row in structured.items()
                if uid in annotation_by_id
            ),
        },
        "error_cases": [
            {
                "id": row["id"],
                "fold": data[row["id"]]["fold"],
                "label": row["primary_label"],
                "confidence": row["confidence"],
                "evidence": row["evidence"],
            }
            for row in annotations
            if row["primary_label"] != "CORRECT"
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in ("dataset_records", "frozen_cohort_records", "labels", "methods", "disagreement")}, indent=2))


if __name__ == "__main__":
    main()
