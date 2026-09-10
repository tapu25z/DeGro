#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path


METHODS = {"self_review", "grounded_self_review", "nonunique", "nonunique_grounding"}
SOURCES = {
    "gpt_oss_20b": (
        ("pilot80", Path("results/gpt_oss_20b_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/gpt_oss_20b_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/gpt-oss_20b_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
    "gemma4_31b": (
        ("pilot80", Path("results/gemma4_31b_mira_pilot80_current_four_methods_complete.jsonl")),
        ("heldout100", Path("results/gemma4_31b_mira_four_methods_complete.jsonl")),
        ("confirmatory120", Path("results/gemma4_31b_mira_confirmatory_remaining_120_complete.jsonl")),
    ),
}


def main() -> None:
    for model, sources in SOURCES.items():
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
