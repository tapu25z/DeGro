#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

from targetcheck.error_taxonomy import blank_annotation


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a blinded DRAW-1K natural-error cohort.")
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--data", type=Path, default=Path("data/draw1k/draw1k.jsonl"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--study-name", default="DRAW-1K test-split natural-error study")
    args = parser.parse_args()
    source = {row["unique_id"]: row for row in map(json.loads, args.data.read_text().splitlines())}
    chosen = {}
    for pattern in args.patterns:
        for filename in sorted(glob.glob(pattern)):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                if row.get("method") != "structured_solver":
                    continue
                if row["id"] not in chosen or chosen[row["id"]].get("status") == "error":
                    chosen[row["id"]] = row
    packet, excluded = [], {}
    for uid, result in sorted(chosen.items()):
        if result.get("status") != "ok":
            reason = result.get("status", "missing_status")
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        if result.get("initial_verdict") not in {"DETERMINATE", "AMBIGUOUS"}:
            reason = f"solver_{str(result.get('initial_verdict', 'missing')).lower()}"
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        item = source[uid]
        reference = "Gold equation system: " + json.dumps(item["gold_equations"]) + "\nGold derivation template: " + json.dumps(item["gold_template"])
        packet.append({
            "id": uid,
            "split": item["split"],
            "problem": item["problem"],
            "reference_solution": reference,
            "reference_answer": item["gold_solutions"],
            "gold_alignment": item["alignment"],
            "generated_formalization": result["formalization"],
        })
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in packet)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.out_dir / "adjudication_packet.jsonl"
    packet_path.write_text(payload)
    for name in ("a", "b"):
        path = args.out_dir / f"annotations_{name}.jsonl"
        if path.exists():
            raise SystemExit(f"Refusing to overwrite annotations: {path}")
        path.write_text("".join(json.dumps(blank_annotation(row["id"]), separators=(",", ":")) + "\n" for row in packet))
    manifest = {
        "study": args.study_name,
        "unit": "one original problem and its shared joint-target formalization",
        "source_results": len(chosen),
        "records": len(packet),
        "excluded": excluded,
        "packet_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "blinded_fields": ["initial_verdict", "witnesses", "repair", "correct", "method outcome"],
        "source_patterns": args.patterns,
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
