#!/usr/bin/env python3
"""Validate reviewed DRAW-Paired candidates and freeze approved pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from targetcheck import Constraint, ModelSpec, check_target_determinacy
from targetcheck.determinacy import CheckStatus

try:
    from scripts.build_draw_paired import read_jsonl, sha256, write_jsonl
except ModuleNotFoundError:  # Direct execution places scripts/ rather than the repo root on sys.path.
    from build_draw_paired import read_jsonl, sha256, write_jsonl


DEFAULT_REVIEW = Path("data/paired/draw_paired/review_packet.jsonl")
DEFAULT_OUT = Path("data/paired/draw_paired/draw_paired.jsonl")


def _approved_span(row: dict[str, Any]) -> tuple[str, str]:
    review = row.get("review") or {}
    if review.get("status") != "APPROVE":
        raise ValueError("review status is not APPROVE")
    if not str(review.get("reviewer") or "").strip():
        raise ValueError("approved row has no reviewer")
    if review.get("meaning_preserved_after_deletion") is not True:
        raise ValueError("semantic-preservation check is not true")
    source_span = review.get("source_span_exact")
    underspecified = review.get("underspecified_problem")
    if not isinstance(source_span, str) or not source_span.strip():
        raise ValueError("approved row has no exact source span")
    if not isinstance(underspecified, str) or not underspecified.strip():
        raise ValueError("approved row has no underspecified problem")
    original = row["original_problem"]
    if original.count(source_span) != 1:
        raise ValueError("exact source span must occur exactly once in the original")
    expected = original.replace(source_span, "", 1)
    if " ".join(expected.split()) != " ".join(underspecified.split()):
        raise ValueError("underspecified problem is not exactly the reviewed span deletion")
    return source_span, underspecified


def _revalidate(row: dict[str, Any]) -> None:
    base = ModelSpec.from_dict(row["base_spec"])
    missing_raw = dict(row["missing_constraint"])
    missing = Constraint.from_dict(missing_raw)
    base_result = check_target_determinacy(base)
    full = ModelSpec(base.variables, base.constraints + (missing,), base.target, base.metadata)
    full_result = check_target_determinacy(full)
    if base_result.status != CheckStatus.AMBIGUOUS:
        raise ValueError(f"base is {base_result.status}, not AMBIGUOUS")
    if full_result.status != CheckStatus.DETERMINATE:
        raise ValueError(f"full model is {full_result.status}, not DETERMINATE")
    if full_result.target_value != row["gold_target"]:
        raise ValueError("recomputed target does not match candidate gold target")


def paired_cases(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source_span, underspecified = _approved_span(row)
    _revalidate(row)
    missing = {**row["missing_constraint"], "source_span": source_span, "provenance": "EXPLICIT_TEXT"}
    shared = {
        "pair_id": row["candidate_id"],
        "family": "draw_natural_algebra",
        "difficulty": "natural",
        "source_id": row["source_id"],
        "source_index": row["source_index"],
        "source_split": row["split"],
        "spec": row["base_spec"],
        "gold_target": row["gold_target"],
    }
    return (
        {**shared, "label": "OMISSION", "problem": row["original_problem"], "missing_constraint": missing},
        {**shared, "label": "UNDERSPECIFIED", "problem": underspecified, "missing_constraint": None},
    )


def finalize(review_path: Path, out_path: Path, allow_partial: bool = False) -> dict[str, Any]:
    rows = list(read_jsonl(review_path))
    statuses = Counter((row.get("review") or {}).get("status", "MISSING") for row in rows)
    pending = sum(count for status, count in statuses.items() if status not in {"APPROVE", "REJECT"})
    if pending and not allow_partial:
        raise ValueError(f"{pending} rows are not reviewed; use --allow-partial only for an explicit partial freeze")

    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in rows:
        if (row.get("review") or {}).get("status") != "APPROVE":
            continue
        try:
            cases.extend(paired_cases(row))
        except ValueError as exc:
            errors.append(f"{row.get('candidate_id')}: {exc}")
    if errors:
        raise ValueError("invalid approved reviews:\n" + "\n".join(errors))
    if not cases:
        raise ValueError("no approved pairs to freeze")

    write_jsonl(out_path, cases)
    manifest = {
        "dataset_name": "DRAW-Paired",
        "stage": "FROZEN",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "review_packet": str(review_path),
        "review_packet_sha256": sha256(review_path),
        "review_status_counts": dict(sorted(statuses.items())),
        "allow_partial": allow_partial,
        "pairs": len(cases) // 2,
        "cases": len(cases),
        "output_sha256": sha256(out_path),
        "human_review_complete": pending == 0,
        "frozen": True,
    }
    out_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    print(json.dumps(finalize(args.review, args.out, args.allow_partial), indent=2))


if __name__ == "__main__":
    main()
