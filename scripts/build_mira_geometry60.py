#!/usr/bin/env python3
"""Freeze the validated Geometry60 slice of the MIRA near-fragment extension."""
import hashlib
import json
from pathlib import Path

SOURCE = Path("data/paired/mira_near_fragment_174.jsonl")
SOURCE_MANIFEST = SOURCE.with_suffix(".manifest.json")
OUTPUT = Path("data/paired/mira_geometry_60.jsonl")


def main():
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
    selected = [row for row in rows if row["family"] == "geometry_coordinates"]
    assert len(selected) == 120 and len({row["pair_id"] for row in selected}) == 60
    assert {row["label"] for row in selected} == {"OMISSION", "UNDERSPECIFIED"}
    content = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in selected)
    OUTPUT.write_text(content)
    source_manifest = json.loads(SOURCE_MANIFEST.read_text())
    manifest = {
        "study": "Geometry60 extension to MIRA-300; separate until all-model analysis is complete",
        "source_dataset": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "mira_source_sha256": source_manifest["source_sha256"],
        "family": "geometry_coordinates", "pairs": 60, "cases": 120,
        "selection": "all 60 geometry instances in the frozen MIRA-Math release; no outcome-based filtering",
        "target_representation": "squared Euclidean distance; uniqueness-equivalent to nonnegative Euclidean distance",
        "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    OUTPUT.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
