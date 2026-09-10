#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from targetcheck.error_taxonomy import ErrorLabel, NaturalErrorAnnotation


def load(path: Path) -> dict[str, dict]:
    return {row["id"]: row for row in map(json.loads, path.read_text().splitlines())}


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize dual-AI labels after required human adjudication and audit.")
    parser.add_argument("annotation_a", type=Path)
    parser.add_argument("annotation_b", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    a, b, reviews = load(args.annotation_a), load(args.annotation_b), load(args.review)
    if set(a) != set(b):
        raise SystemExit("annotation ID mismatch")
    resolved = []
    for uid in sorted(a):
        same = (a[uid]["primary_label"], a[uid]["target_critical_underformalization"]) == (
            b[uid]["primary_label"], b[uid]["target_critical_underformalization"]
        )
        if uid in reviews:
            raw = reviews[uid].get("resolution")
            if not isinstance(raw, dict):
                raise SystemExit(f"missing human resolution for required review: {uid}")
            raw = {"id": uid, **raw}
            process = "DUAL_AI_HUMAN_ADJUDICATED" if not same else "DUAL_AI_HUMAN_AUDITED"
        elif same:
            raw = {"id": uid, **a[uid]}
            process = "DUAL_AI_CONSENSUS_UNAUDITED"
        else:
            raise SystemExit(f"model disagreement is absent from review queue: {uid}")
        annotation = NaturalErrorAnnotation.from_dict(raw)
        if annotation.primary_label == ErrorLabel.UNSURE:
            raise SystemExit(f"UNSURE is not a final label: {uid}")
        resolved.append({**asdict(annotation), "annotation_process": process})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in resolved))
    print(json.dumps({"records": len(resolved), "human_reviewed": len(reviews), "consensus_unaudited": len(resolved) - len(reviews)}))


if __name__ == "__main__":
    main()
