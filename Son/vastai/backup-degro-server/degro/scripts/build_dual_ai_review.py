#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def load(path: Path) -> dict[str, dict]:
    return {row["id"]: row for row in map(json.loads, path.read_text().splitlines())}


def label_key(row: dict) -> tuple[str, bool]:
    return row["primary_label"], bool(row["target_critical_underformalization"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze disagreements and a deterministic consensus audit sample.")
    parser.add_argument("annotation_a", type=Path)
    parser.add_argument("annotation_b", type=Path)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit-rate", type=float, default=0.2)
    args = parser.parse_args()
    if not 0 <= args.audit_rate <= 1:
        raise SystemExit("audit rate must be between 0 and 1")
    a, b, packet = load(args.annotation_a), load(args.annotation_b), load(args.packet)
    if set(a) != set(b) or set(a) != set(packet):
        raise SystemExit("annotation and packet IDs must match exactly")
    disagreements = {uid for uid in a if label_key(a[uid]) != label_key(b[uid])}
    consensus_by_label: dict[str, list[str]] = {}
    for uid in sorted(set(a) - disagreements):
        consensus_by_label.setdefault(a[uid]["primary_label"], []).append(uid)
    audit = set()
    for label, ids in consensus_by_label.items():
        ranked = sorted(ids, key=lambda uid: hashlib.sha256(f"natural-error-audit-v1:{uid}".encode()).hexdigest())
        count = math.ceil(args.audit_rate * len(ranked))
        audit.update(ranked[:count])
        if label == "MISSING_CONSTRAINT":
            audit.update(ranked)
    queue = []
    for uid in sorted(disagreements | audit):
        context = packet[uid]
        queue.append({
            "id": uid,
            "review_reason": "MODEL_DISAGREEMENT" if uid in disagreements else "CONSENSUS_AUDIT",
            "problem": context["problem"],
            "reference_solution": context["reference_solution"],
            "reference_answer": context["reference_answer"],
            "generated_formalization": context["generated_formalization"],
            "proposal_a": {key: a[uid][key] for key in ("primary_label", "target_critical_underformalization", "evidence", "notes", "confidence", "ai_model")},
            "proposal_b": {key: b[uid][key] for key in ("primary_label", "target_critical_underformalization", "evidence", "notes", "confidence", "ai_model")},
            "resolution": None,
        })
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in queue)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise SystemExit(f"Refusing to overwrite existing review decisions: {args.out}")
    args.out.write_text(payload)
    manifest = {
        "cohort_records": len(a),
        "model_disagreements": len(disagreements),
        "consensus_records": len(a) - len(disagreements),
        "consensus_audit_records": len(audit),
        "human_review_queue": len(queue),
        "audit_rule": "all consensus MISSING_CONSTRAINT plus deterministic label-stratified ceiling sample",
        "audit_rate": args.audit_rate,
        "selection_salt": "natural-error-audit-v1",
        "queue_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
