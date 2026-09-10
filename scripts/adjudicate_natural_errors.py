#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from targetcheck.error_taxonomy import ErrorLabel, NaturalErrorAnnotation


def load(path: Path) -> dict[str, NaturalErrorAnnotation]:
    rows: dict[str, NaturalErrorAnnotation] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            annotation = NaturalErrorAnnotation.from_dict(json.loads(line))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"{path}:{line_number}: {exc}") from exc
        if annotation.id in rows:
            raise SystemExit(f"{path}:{line_number}: duplicate id {annotation.id}")
        rows[annotation.id] = annotation
    return rows


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    if not labels_a:
        return 0.0
    n = len(labels_a)
    observed = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    counts_a, counts_b = Counter(labels_a), Counter(labels_b)
    expected = sum(counts_a[label] * counts_b[label] for label in set(counts_a) | set(counts_b)) / (n * n)
    return 1.0 if expected == 1.0 and observed == 1.0 else (observed - expected) / (1.0 - expected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate two blind annotation passes and prepare disagreements.")
    parser.add_argument("annotation_a", type=Path)
    parser.add_argument("annotation_b", type=Path)
    parser.add_argument("--disagreements", type=Path, required=True)
    parser.add_argument("--agreement-out", type=Path, required=True)
    args = parser.parse_args()
    a, b = load(args.annotation_a), load(args.annotation_b)
    if set(a) != set(b):
        raise SystemExit(f"annotation ID mismatch: only A={sorted(set(a)-set(b))[:5]}, only B={sorted(set(b)-set(a))[:5]}")
    unfinished = [uid for uid in a if a[uid].primary_label == ErrorLabel.UNSURE or b[uid].primary_label == ErrorLabel.UNSURE]
    if unfinished:
        raise SystemExit(f"UNSURE annotations remain ({len(unfinished)}), first IDs: {unfinished[:5]}")
    ids = sorted(a)
    labels_a = [a[uid].primary_label.value for uid in ids]
    labels_b = [b[uid].primary_label.value for uid in ids]
    disagreements = []
    for uid in ids:
        if (a[uid].primary_label, a[uid].target_critical_underformalization) != (b[uid].primary_label, b[uid].target_critical_underformalization):
            disagreements.append({
                "id": uid,
                "annotation_a": a[uid].__dict__,
                "annotation_b": b[uid].__dict__,
                "resolution": None,
            })
    args.disagreements.parent.mkdir(parents=True, exist_ok=True)
    args.disagreements.write_text("".join(json.dumps(row, default=str, separators=(",", ":")) + "\n" for row in disagreements))
    report = {
        "records": len(ids),
        "exact_label_agreement": sum(x == y for x, y in zip(labels_a, labels_b)) / len(ids) if ids else 0.0,
        "cohen_kappa": cohen_kappa(labels_a, labels_b),
        "target_subset_agreement": sum(
            a[uid].target_critical_underformalization == b[uid].target_critical_underformalization for uid in ids
        ) / len(ids) if ids else 0.0,
        "disagreements": len(disagreements),
        "labels_a": dict(Counter(labels_a)),
        "labels_b": dict(Counter(labels_b)),
    }
    args.agreement_out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
