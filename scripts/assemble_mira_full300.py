#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


METHODS = {"self_review", "grounded_self_review", "nonunique", "nonunique_grounding"}
SOURCES = {
    "nemotron_3_ultra": (
        ("pilot80", Path("results/nemotron_3_ultra_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/nemotron_3_ultra_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/nemotron_3_ultra_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
    "nemotron_3_super": (
        ("pilot80", Path("results/nemotron_3_super_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/nemotron_3_super_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/nemotron_3_super_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
    "nemotron_3_nano_30b": (
        ("pilot80", Path("results/nemotron_3_nano_30b_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/nemotron_3_nano_30b_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/nemotron_3_nano_30b_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
    "gpt_oss_20b": (
        ("pilot80", Path("results/gpt_oss_20b_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/gpt_oss_20b_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/gpt-oss_20b_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
    "gpt_oss_120b": (
        ("pilot80", Path("results/gpt_oss_120b_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/gpt_oss_120b_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/gpt_oss_120b_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=tuple(SOURCES), default=["gpt_oss_20b", "gpt_oss_120b"])
    args = parser.parse_args()
    for model in args.models:
        sources = SOURCES[model]
        records = {}
        split_counts = {}
        for split, path in sources:
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            split_counts[split] = len(rows)
            for row in rows:
                if row.get("status") != "ok" or row["method"] not in METHODS:
                    raise SystemExit(f"incomplete or unexpected row in {path}")
                key = (row["pair_id"], row["label"], row["method"])
                if key in records:
                    raise SystemExit(f"duplicate key across splits: {key}")
                records[key] = {**row, "evaluation_split": split}
        if len(records) != 300 * 2 * 4:
            raise SystemExit(f"{model}: expected 2400 records, found {len(records)}")
        output = Path(f"results/{model}_mira_full300_complete.jsonl")
        output.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records.values()))
        with Path(f"results/{model}_mira_full300_summary.tsv").open("w") as stream:
            subprocess.run([".venv/bin/python", "scripts/analyze_pilot.py", str(output)], check=True, stdout=stream)
        with Path(f"results/{model}_mira_full300_analysis.json").open("w") as stream:
            subprocess.run([".venv/bin/python", "scripts/analyze_confirmatory.py", str(output)], check=True, stdout=stream)
        print(json.dumps({"model": model, "records": len(records), "split_counts": split_counts}))


if __name__ == "__main__":
    main()
