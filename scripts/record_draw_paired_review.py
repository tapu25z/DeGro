#!/usr/bin/env python3
"""Record an author's completed review of the locked DRAW-Paired cohort."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_PACKET = Path("data/paired/draw_paired/draw_paired_provisional_300_review.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--approve-all-reviewed", action="store_true")
    args = parser.parse_args()
    if not args.approve_all_reviewed:
        raise SystemExit("refusing bulk approval without --approve-all-reviewed")

    rows = [json.loads(line) for line in args.packet.read_text().splitlines() if line.strip()]
    timestamp = datetime.now(UTC).isoformat()
    for row in rows:
        proposal = row["span_proposal"]
        row["review"] = {
            "status": "APPROVE",
            "reviewer": args.reviewer,
            "reviewed_at_utc": timestamp,
            "source_span_exact": proposal["source_span"],
            "underspecified_problem": proposal["underspecified_problem"],
            "meaning_preserved_after_deletion": True,
            "notes": "Author confirmed the locked cohort after manual review.",
        }
    args.packet.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    )
    print(json.dumps({"packet": str(args.packet), "approved": len(rows), "reviewer": args.reviewer}))


if __name__ == "__main__":
    main()
