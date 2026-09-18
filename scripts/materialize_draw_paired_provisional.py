#!/usr/bin/env python3
"""Lock a provisional 300-pair DRAW cohort before model inference.

The resulting cases use only unflagged automatic span proposals. They remain
provisional until a human approves the exact same source spans and deletions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from targetcheck.pilot import score

try:
    from scripts.build_draw_paired import read_jsonl, review_row, sha256, write_jsonl
except ModuleNotFoundError:  # Direct execution places scripts/ rather than the repo root on sys.path.
    from build_draw_paired import read_jsonl, review_row, sha256, write_jsonl


DEFAULT_CANDIDATES = Path("data/paired/draw_paired/candidates.jsonl")
DEFAULT_OUT = Path("data/paired/draw_paired/draw_paired_provisional_300.jsonl")
SEED = 20260918


def _rank(candidate_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{candidate_id}".encode()).hexdigest()


def _allocate(counts: dict[str, int], total: int) -> dict[str, int]:
    available = sum(counts.values())
    raw = {key: total * value / available for key, value in counts.items()}
    allocation = {key: int(value) for key, value in raw.items()}
    remainder = total - sum(allocation.values())
    order = sorted(counts, key=lambda key: (-(raw[key] - allocation[key]), key))
    for key in order[:remainder]:
        allocation[key] += 1
    return allocation


def _cases(candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    proposal = candidate["span_proposal"]
    missing = {
        **candidate["missing_constraint"],
        "source_span": proposal["source_span"],
        "provenance": "EXPLICIT_TEXT",
    }
    shared = {
        "pair_id": candidate["candidate_id"],
        "family": "draw_natural_algebra",
        "difficulty": "natural",
        "source_id": candidate["source_id"],
        "source_index": candidate["source_index"],
        "source_split": candidate["split"],
        "spec": candidate["base_spec"],
        "gold_target": candidate["gold_target"],
        "dataset_stage": "PROVISIONAL_AWAITING_HUMAN_REVIEW",
    }
    return (
        {
            **shared,
            "label": "OMISSION",
            "problem": candidate["original_problem"],
            "missing_constraint": missing,
        },
        {
            **shared,
            "label": "UNDERSPECIFIED",
            "problem": proposal["underspecified_problem"],
            "missing_constraint": None,
        },
    )


def _validate_oracle(case: dict[str, Any]) -> None:
    if case["label"] == "OMISSION":
        missing = case["missing_constraint"]
        output = {
            "decision": "ADD_CONSTRAINT",
            "source_span": missing["source_span"],
            "constraint": missing["expression"],
        }
    else:
        output = {"decision": "ABSTAIN", "source_span": None, "constraint": None}
    result = score(case, output)
    if not result["correct"]:
        raise ValueError(f"oracle failed for {case['pair_id']} {case['label']}: {result}")


def materialize(candidates_path: Path, out_path: Path, pairs: int, seed: int) -> dict[str, Any]:
    candidates = [row for row in read_jsonl(candidates_path) if not row["span_proposal"]["flags"] and not row.get("excluded_from_evaluation")]
    by_split: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_split.setdefault(candidate["split"], []).append(candidate)
    if len(candidates) < pairs:
        raise ValueError(f"only {len(candidates)} unflagged candidates for {pairs} requested pairs")
    allocation = _allocate({key: len(value) for key, value in by_split.items()}, pairs)
    selected = []
    for split, rows in sorted(by_split.items()):
        ranked = sorted(rows, key=lambda row: _rank(row["candidate_id"], seed))
        selected.extend(ranked[: allocation[split]])
    selected.sort(key=lambda row: _rank(row["candidate_id"], seed))

    cases = [case for candidate in selected for case in _cases(candidate)]
    for case in cases:
        _validate_oracle(case)
    write_jsonl(out_path, cases)
    review_path = out_path.with_name(out_path.stem + "_review.jsonl")
    write_jsonl(
        review_path,
        (review_row(candidate, rank) for rank, candidate in enumerate(selected, 1)),
    )
    manifest = {
        "dataset_name": "DRAW-Paired",
        "stage": "PROVISIONAL_AWAITING_HUMAN_REVIEW",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "candidate_path": str(candidates_path),
        "candidate_sha256": sha256(candidates_path),
        "selection_seed": seed,
        "selection_rule": "unflagged span proposals; proportional source-split allocation; SHA-256 seeded rank",
        "available_unflagged_pairs": len(candidates),
        "pairs": len(selected),
        "cases": len(cases),
        "pairs_by_split": dict(sorted(Counter(row["split"] for row in selected).items())),
        "oracle_score_checks": len(cases),
        "output_sha256": sha256(out_path),
        "cohort_review_packet": str(review_path),
        "cohort_review_packet_sha256": sha256(review_path),
        "human_review_complete": False,
        "frozen": False,
        "claim_scope": "exploratory/provisional only until exact spans and deletions are human-approved",
    }
    out_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pairs", type=int, default=300)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    print(json.dumps(materialize(args.candidates, args.out, args.pairs, args.seed), indent=2))


if __name__ == "__main__":
    main()
