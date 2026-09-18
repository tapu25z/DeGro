#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import math
from collections import Counter
from pathlib import Path

from targetcheck.error_taxonomy import ErrorLabel, NaturalErrorAnnotation


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def proportion(successes: int, total: int) -> dict:
    return {"successes": successes, "total": total, "rate": successes / total if total else None, "wilson_95_ci": wilson(successes, total)}


def mcnemar_exact(b: int, c: int) -> float | None:
    n = b + c
    if n == 0:
        return None
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def load_results(patterns: list[str]) -> dict[tuple[str, str], dict]:
    chosen = {}
    for pattern in patterns:
        for filename in sorted(glob.glob(pattern)):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                key = (row["id"], row["method"])
                if key not in chosen or chosen[key].get("status") == "error":
                    chosen[key] = row
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a resolved, blinded natural-error study.")
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    annotations = {}
    for line_number, line in enumerate(args.annotations.read_text().splitlines(), 1):
        try:
            annotation = NaturalErrorAnnotation.from_dict(json.loads(line))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"{args.annotations}:{line_number}: {exc}") from exc
        if annotation.primary_label == ErrorLabel.UNSURE:
            raise SystemExit(f"{args.annotations}:{line_number}: unresolved UNSURE label")
        annotations[annotation.id] = annotation
    results = load_results(args.patterns)
    joined = []
    missing = []
    for uid, annotation in annotations.items():
        structured = results.get((uid, "structured_solver"))
        degro = results.get((uid, "degro"))
        if structured is None or degro is None:
            missing.append(uid)
            continue
        joined.append((annotation, structured, degro))
    if missing:
        raise SystemExit(f"missing structured_solver/degro results for {len(missing)} IDs: {missing[:5]}")

    positives = [row for row in joined if row[0].target_critical_underformalization]
    negatives = [row for row in joined if not row[0].target_critical_underformalization]
    correct_controls = [row for row in joined if row[0].primary_label == ErrorLabel.CORRECT]
    detected = lambda row: row[1].get("initial_verdict") == "AMBIGUOUS"
    repaired = lambda row: detected(row) and bool(row[2].get("changed")) and bool(row[2].get("correct"))
    false_repair = lambda row: bool(row[2].get("changed")) and row[0].primary_label != ErrorLabel.MISSING_CONSTRAINT
    detector_tp = sum(detected(row) for row in positives)
    detector_fp = sum(detected(row) for row in negatives)
    baseline_wins = sum(bool(s.get("correct")) and not bool(d.get("correct")) for _, s, d in joined)
    degro_wins = sum(not bool(s.get("correct")) and bool(d.get("correct")) for _, s, d in joined)
    by_label = {}
    for label in ErrorLabel:
        if label == ErrorLabel.UNSURE:
            continue
        subset = [row for row in joined if row[0].primary_label == label]
        if not subset:
            continue
        by_label[label.value] = {
            "records": len(subset),
            "ambiguity_detected": proportion(sum(detected(row) for row in subset), len(subset)),
            "accepted_repair": proportion(sum(bool(row[2].get("changed")) for row in subset), len(subset)),
            "structured_solver_correct": proportion(sum(bool(row[1].get("correct")) for row in subset), len(subset)),
            "degro_correct": proportion(sum(bool(row[2].get("correct")) for row in subset), len(subset)),
        }
    report = {
        "records": len(joined),
        "taxonomy": dict(Counter(row[0].primary_label.value for row in joined)),
        "by_label": by_label,
        "primary_subset": len(positives),
        "detector_recall_on_target_critical_missing_constraints": proportion(detector_tp, len(positives)),
        "detector_precision": proportion(detector_tp, detector_tp + detector_fp),
        "repair_success_on_target_critical_missing_constraints": proportion(sum(repaired(row) for row in positives), len(positives)),
        "conditional_repair_success_after_detection": proportion(sum(repaired(row) for row in positives), detector_tp),
        "false_ambiguity_outside_primary_subset": proportion(detector_fp, len(negatives)),
        "false_repair_on_out_of_scope_errors": proportion(sum(false_repair(row) for row in negatives), len(negatives)),
        "correct_control_preservation": proportion(sum(bool(row[2].get("correct")) for row in correct_controls), len(correct_controls)),
        "end_to_end": {
            "structured_solver_accuracy": proportion(sum(bool(row[1].get("correct")) for row in joined), len(joined)),
            "degro_accuracy": proportion(sum(bool(row[2].get("correct")) for row in joined), len(joined)),
            "discordant_structured_wins": baseline_wins,
            "discordant_degro_wins": degro_wins,
            "mcnemar_exact_p": mcnemar_exact(baseline_wins, degro_wins),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
