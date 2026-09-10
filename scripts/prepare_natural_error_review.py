#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path


CONFIDENCE_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge AI proposals into a human-verification queue.")
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=int)
    parser.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    best = {}
    for pattern in args.patterns:
        for filename in sorted(glob.glob(pattern)):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                if row.get("status") == "ok":
                    best[row["id"]] = row
    contexts = {row["id"]: row for row in map(json.loads, args.packet.read_text().splitlines())}
    queue = []
    for uid, row in best.items():
        if uid not in contexts:
            raise SystemExit(f"proposal ID is absent from the blinded packet: {uid}")
        proposal = row["proposal"]
        queue.append({
            "id": uid,
            "problem": contexts[uid]["problem"],
            "reference_solution": contexts[uid]["reference_solution"],
            "reference_answer": contexts[uid]["reference_answer"],
            "generated_formalization": contexts[uid]["generated_formalization"],
            **proposal,
            "review_status": "PENDING",
            "ai_model": row["model"],
            "ai_prompt_sha256": row["prompt_sha256"],
        })
    queue.sort(key=lambda row: (CONFIDENCE_ORDER.get(row["confidence"], -1), row["id"]))
    if args.expected is not None and len(queue) != args.expected:
        raise SystemExit(f"Expected {args.expected} successful proposals, found {len(queue)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"Refusing to overwrite an existing review file: {args.out}")
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in queue)
    args.out.write_text(payload)
    manifest = {
        "process": "AI-assisted annotation pending human verification",
        "records": len(queue),
        "review_queue_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "models": sorted({row["ai_model"] for row in queue}),
        "prompt_sha256": sorted({row["ai_prompt_sha256"] for row in queue}),
        "source_patterns": args.patterns,
        "packet": str(args.packet),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"records": len(queue), "pending": len(queue)}))


if __name__ == "__main__":
    main()
