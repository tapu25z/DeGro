#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from collections import Counter
from pathlib import Path

from targetcheck.error_taxonomy import NaturalErrorAnnotation


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge final AI adjudications into the ALG514 proposal set.")
    parser.add_argument("--annotations", type=Path, default=Path("data/natural_errors/gpt-oss_20b_alg514_all/gpt_oss_120b_annotations.jsonl"))
    parser.add_argument("--adjudication-pattern", default="results/raw/gpt_oss_120b_alg514_final_adjudication_shard*.jsonl")
    parser.add_argument("--expected", type=int, default=22)
    parser.add_argument("--out", type=Path, default=Path("data/natural_errors/gpt-oss_20b_alg514_all/gpt_oss_120b_ai_adjudicated_labels.jsonl"))
    args = parser.parse_args()

    original = {row["id"]: row for row in map(json.loads, args.annotations.read_text().splitlines())}
    decisions = {}
    for filename in sorted(glob.glob(args.adjudication_pattern)):
        for line in Path(filename).read_text().splitlines():
            row = json.loads(line)
            if row.get("status") == "ok":
                decisions[row["id"]] = row
    if len(decisions) != args.expected:
        raise SystemExit(f"Expected {args.expected} successful decisions, found {len(decisions)}")

    output = []
    for uid in sorted(original):
        row = original[uid]
        if uid in decisions:
            proposal = decisions[uid]["proposal"]
            NaturalErrorAnnotation.from_dict({"id": uid, **proposal})
            output.append({
                "id": uid,
                **proposal,
                "annotation_process": "GPT_OSS_120B_FINAL_AI_ADJUDICATION",
                "prior_label": row["primary_label"],
                "adjudication_think": decisions[uid]["think"],
                "adjudication_prompt_sha256": decisions[uid]["prompt_sha256"],
            })
        else:
            proposal = {key: row[key] for key in ("primary_label", "target_critical_underformalization", "evidence", "notes", "confidence")}
            output.append({
                "id": uid,
                **proposal,
                "annotation_process": "GPT_OSS_120B_INITIAL_AI_PROPOSAL_UNADJUDICATED",
            })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in output)
    args.out.write_text(payload)
    counts = Counter(row["primary_label"] for row in output)
    transitions = Counter((row["prior_label"], row["primary_label"]) for row in output if "prior_label" in row)
    manifest = {
        "status": "GPT-OSS 120B AI-adjudicated labels; not human verified",
        "records": len(output),
        "ai_adjudicated": len(decisions),
        "changed_by_adjudication": sum(before != after for before, after in transitions.elements()),
        "labels": dict(sorted(counts.items())),
        "transitions": {f"{before}->{after}": count for (before, after), count in sorted(transitions.items())},
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "source_annotations": str(args.annotations),
        "source_adjudications": args.adjudication_pattern,
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
