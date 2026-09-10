#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

from targetcheck.error_taxonomy import blank_annotation


def load_best(patterns: list[str]) -> dict[tuple[str, str], dict]:
    chosen: dict[tuple[str, str], dict] = {}
    for pattern in patterns:
        for filename in sorted(glob.glob(pattern)):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                key = (row["id"], row["method"])
                if key not in chosen or chosen[key].get("status") == "error":
                    chosen[key] = row
    return chosen


def write_jsonl(path: Path, rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a blinded natural-error adjudication cohort.")
    parser.add_argument("patterns", nargs="+", help="JSONL result globs from run_math500_six_methods.py")
    parser.add_argument("--data", type=Path, default=Path("data/math500/test.jsonl"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--annotators", nargs="+", default=["a", "b"])
    parser.add_argument("--include-status", choices=("ok", "all"), default="ok")
    args = parser.parse_args()

    source = {row["unique_id"]: row for row in map(json.loads, args.data.read_text().splitlines())}
    results = load_best(args.patterns)
    packet = []
    excluded = {}
    for (uid, method), row in sorted(results.items()):
        if method != "structured_solver" or uid not in source:
            continue
        if args.include_status == "ok" and row.get("status") != "ok":
            excluded[row.get("status", "missing_status")] = excluded.get(row.get("status", "missing_status"), 0) + 1
            continue
        formalization = row.get("formalization")
        if not isinstance(formalization, dict) or formalization.get("status") != "SUPPORTED":
            excluded["no_supported_formalization"] = excluded.get("no_supported_formalization", 0) + 1
            continue
        # Eligibility uses only whether the fixed solver fragment produced a
        # conclusive verdict, never which of the two conclusive verdicts it was.
        # The verdict itself remains absent from the annotation packet.
        if row.get("initial_verdict") not in {"DETERMINATE", "AMBIGUOUS"}:
            reason = f"solver_{str(row.get('initial_verdict', 'missing')).lower()}"
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        problem = source[uid]
        packet.append({
            "id": uid,
            "subject": problem["subject"],
            "level": problem["level"],
            "problem": problem["problem"],
            "reference_solution": problem.get("solution"),
            "reference_answer": problem["answer"],
            "generated_formalization": formalization,
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.out_dir / "adjudication_packet.jsonl"
    packet_hash = write_jsonl(packet_path, packet)
    template_hashes = {}
    for name in args.annotators:
        template_path = args.out_dir / f"annotations_{name}.jsonl"
        if template_path.exists():
            raise SystemExit(f"Refusing to overwrite existing annotations: {template_path}")
        template_hashes[name] = write_jsonl(template_path, [blank_annotation(row["id"]) for row in packet])
    manifest = {
        "study": "blinded natural-error adjudication",
        "unit": "original problem and its single shared initial formalization",
        "records": len(packet),
        "packet_sha256": packet_hash,
        "annotation_template_sha256": template_hashes,
        "excluded": excluded,
        "source_patterns": args.patterns,
        "blinded_fields": ["initial_verdict", "method", "repair", "changed", "correct"],
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
