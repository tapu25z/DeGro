#!/usr/bin/env python3
"""Combine the frozen MIRA-300 main records with the Geometry60 extension."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/mira360_geometry"
SOURCES = {
    "gpt_oss_20b": (
        ROOT / "results/gpt_oss_20b_mira_full300_complete.jsonl",
        ROOT / "results/mira_geometry60/gpt_oss_20b_mira_geometry60_complete.jsonl",
    ),
    "gpt_oss_120b": (
        ROOT / "results/gpt_oss_120b_mira_full300_complete.jsonl",
        ROOT / "results/mira_geometry60/gpt_oss_120b_mira_geometry60_complete.jsonl",
    ),
    "nemotron_3_nano_30b": (
        ROOT / "results/nemotron_3_nano_30b_mira_full300_complete.jsonl",
        ROOT / "results/nano_mira_near_fragment_174/nano_mira_near_fragment_174_complete.jsonl",
    ),
}


def main():
    OUT.mkdir(exist_ok=True)
    for stem, (main_path, extension_path) in SOURCES.items():
        main_rows = [json.loads(line) for line in main_path.read_text().splitlines()]
        extension_rows = [json.loads(line) for line in extension_path.read_text().splitlines()
                          if json.loads(line)["family"] == "geometry_coordinates"]
        assert len(main_rows) == 2400 and len(extension_rows) == 480
        assert not ({r["pair_id"] for r in main_rows} & {r["pair_id"] for r in extension_rows})
        rows = ([{**r, "evaluation_cohort": "original_mira300"} for r in main_rows] +
                [{**r, "evaluation_cohort": "geometry60_extension"} for r in extension_rows])
        assert len({(r["pair_id"], r["label"], r["method"]) for r in rows}) == 2880
        output = OUT / f"{stem}_mira360_complete.jsonl"
        output.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
        with (OUT / f"{stem}_summary.tsv").open("w") as stream:
            subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/analyze_pilot.py", str(output)],
                           cwd=ROOT, stdout=stream, check=True)
        with (OUT / f"{stem}_analysis.json").open("w") as stream:
            subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/analyze_confirmatory.py", str(output)],
                           cwd=ROOT, stdout=stream, check=True)
        print(json.dumps({"model": stem, "pairs": 360, "records": len(rows)}))


if __name__ == "__main__":
    main()
