#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "results" / "frozen" / "decision_stage_100pairs_20260909"

ARTIFACTS = (
    "data/paired/mira_heldout_100.jsonl",
    "data/paired/mira_heldout_100.manifest.json",
    "results/gpt_oss_20b_confirmatory_100_complete.jsonl",
    "results/gpt_oss_20b_confirmatory_100_summary.tsv",
    "results/gpt_oss_20b_confirmatory_100_analysis.json",
    "results/gpt_oss_20b_decision_baselines_100_complete.jsonl",
    "results/gpt_oss_20b_decision_baselines_100_summary.tsv",
    "results/gpt_oss_20b_decision_analysis.json",
    "results/decision_baselines_report.md",
)

CODE = (
    "pyproject.toml",
    "targetcheck/compiler_z3.py",
    "targetcheck/determinacy.py",
    "targetcheck/expressions.py",
    "targetcheck/grounding.py",
    "targetcheck/modelspec.py",
    "targetcheck/pilot.py",
    "targetcheck/providers/ollama_cloud.py",
    "scripts/analyze_confirmatory.py",
    "scripts/analyze_pilot.py",
    "scripts/build_heldout_mira.py",
    "scripts/finalize_pilot.py",
    "scripts/run_decision_baselines.sh",
    "scripts/run_heldout_background.sh",
    "scripts/run_pilot.py",
    "tests/test_determinacy.py",
    "tests/test_expressions.py",
    "tests/test_ollama_cloud.py",
    "tests/test_prompts.py",
    "tests/test_scoring.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def copy_allowlisted(relative_path: str) -> None:
    source = ROOT / relative_path
    destination = DESTINATION / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    if (DESTINATION / "freeze_manifest.json").exists():
        raise SystemExit(f"freeze already exists: {DESTINATION}")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for relative_path in ARTIFACTS + CODE:
        copy_allowlisted(relative_path)

    six = load_jsonl(ROOT / ARTIFACTS[2])
    follow_up = load_jsonl(ROOT / ARTIFACTS[5])
    combined = six + follow_up
    manifest = {
        "freeze_id": "decision_stage_100pairs_20260909",
        "frozen_at": "2026-09-09",
        "status": "FROZEN_DO_NOT_TUNE",
        "study_label": "decision-stage follow-up after inspecting initial six-method results",
        "dataset_pairs": len({row["pair_id"] for row in combined}),
        "initial_records": len(six),
        "follow_up_records": len(follow_up),
        "combined_records": len(combined),
        "status_counts": dict(Counter(row["status"] for row in combined)),
        "model_counts": dict(Counter(row["model"] for row in combined)),
        "method_counts": dict(Counter(row["method"] for row in combined)),
        "prompt_hash_counts": dict(Counter(row["prompt_hash"] for row in combined)),
        "excluded": [
            "api.txt and all credentials",
            "partial RandomPair diagnostic records",
            "provider worker logs",
        ],
        "files": {},
    }
    for path in sorted(DESTINATION.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(DESTINATION))
            manifest["files"][relative] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    (DESTINATION / "freeze_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "destination": str(DESTINATION),
        "files": len(manifest["files"]),
        "records": len(combined),
        "sha256_manifest": sha256(DESTINATION / "freeze_manifest.json"),
    }))


if __name__ == "__main__":
    main()
