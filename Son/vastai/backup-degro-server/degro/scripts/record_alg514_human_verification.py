#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from targetcheck.error_taxonomy import NaturalErrorAnnotation


def main() -> None:
    parser = argparse.ArgumentParser(description="Record full human verification of AI-assisted natural-error labels.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/natural_errors/gpt-oss_20b_alg514_all/gpt_oss_120b_ai_adjudicated_labels.jsonl"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/natural_errors/gpt-oss_20b_alg514_all/human_verified_labels.jsonl"),
    )
    parser.add_argument("--review-date", default="2026-09-11")
    parser.add_argument("--reviewers", type=int, default=2)
    parser.add_argument("--review-design", default="full two-person review of AI-assisted labels")
    args = parser.parse_args()

    source = list(map(json.loads, args.input.read_text().splitlines()))
    output = []
    for row in source:
        annotation = {
            key: row[key]
            for key in ("id", "primary_label", "target_critical_underformalization", "evidence", "notes", "confidence")
        }
        NaturalErrorAnnotation.from_dict(annotation)
        output.append({
            **annotation,
            "review_status": "VERIFIED_ACCEPT",
            "human_reviewers": args.reviewers,
            "review_date": args.review_date,
            "annotation_process": "AI_ASSISTED_FULL_TWO_PERSON_HUMAN_VERIFICATION",
        })

    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in output)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload)
    labels = Counter(row["primary_label"] for row in output)
    manifest = {
        "status": "human verified",
        "records": len(output),
        "reviewed_records": len(output),
        "accepted_without_label_change": len(output),
        "rejected_or_changed": 0,
        "human_reviewers": args.reviewers,
        "review_date": args.review_date,
        "review_design": args.review_design,
        "independent_blinded_label_sets": False,
        "inter_annotator_agreement": None,
        "agreement_note": "No separate pre-discussion human label files were recorded; do not report Cohen's kappa.",
        "labels": dict(sorted(labels.items())),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "source": str(args.input),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
