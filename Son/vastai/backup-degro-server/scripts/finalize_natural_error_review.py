#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from targetcheck.error_taxonomy import ErrorLabel, NaturalErrorAnnotation


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate human decisions and emit analysis-ready annotations.")
    parser.add_argument("review", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    resolved = []
    seen = set()
    counts = {"ACCEPTED": 0, "EDITED": 0}
    for line_number, line in enumerate(args.review.read_text().splitlines(), 1):
        raw = json.loads(line)
        uid = raw.get("id")
        if uid in seen:
            raise SystemExit(f"{args.review}:{line_number}: duplicate id {uid}")
        seen.add(uid)
        status = raw.get("review_status")
        if status not in counts:
            raise SystemExit(f"{args.review}:{line_number}: review_status must be ACCEPTED or EDITED")
        try:
            annotation = NaturalErrorAnnotation.from_dict(raw)
        except (ValueError, TypeError) as exc:
            raise SystemExit(f"{args.review}:{line_number}: {exc}") from exc
        if annotation.primary_label == ErrorLabel.UNSURE:
            raise SystemExit(f"{args.review}:{line_number}: UNSURE is not a final label")
        counts[status] += 1
        resolved.append({**asdict(annotation), "annotation_process": "AI_ASSISTED_HUMAN_VERIFIED", "review_status": status})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in resolved))
    print(json.dumps({"records": len(resolved), **counts}))


if __name__ == "__main__":
    main()
