#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path


URL = "https://download.microsoft.com/download/7/5/3/753757BD-CEEB-459C-A4D1-15BF843A5B2C/0.7.zip"
ARCHIVE_SHA256 = "de415ed5d7182c6b4000ec648fbb57b19345f2adc67a69cd95e09912534ec92f"
ROOT = "0.7 - release/"


def normalize(archive: bytes) -> tuple[list[dict], dict]:
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        raw_rows = json.loads(bundle.read(ROOT + "draw.json"))
        splits = {
            name: set(bundle.read(ROOT + f"draw-{name}.txt").decode().split())
            for name in ("train", "dev", "test")
        }
        release_readme = bundle.read(ROOT + "README.txt").decode(errors="replace")
    rows = []
    occurrences: Counter[str] = Counter()
    for raw in raw_rows:
        uid = str(raw["iIndex"])
        occurrences[uid] += 1
        normalized_uid = f"draw1k/{uid}" if occurrences[uid] == 1 else f"draw1k/{uid}-duplicate-{occurrences[uid]}"
        membership = [name for name, ids in splits.items() if uid in ids]
        if len(membership) > 1:
            raise ValueError(f"DRAW-1K ID occurs in multiple splits: {uid}")
        rows.append({
            "unique_id": normalized_uid,
            "source_index": raw["iIndex"],
            "split": membership[0] if membership else "unassigned",
            "problem": raw["sQuestion"],
            "gold_equations": raw["lEquations"],
            "gold_solutions": raw["lSolutions"],
            "gold_template": raw["Template"],
            "alignment": raw["Alignment"],
            "equivalent_alignments": raw["Equiv"],
        })
    rows.sort(key=lambda row: row["source_index"])
    return rows, {"split_source_counts": {name: len(ids) for name, ids in splits.items()}, "release_readme": release_readme}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and normalize the official DRAW-1K release.")
    parser.add_argument("--out", type=Path, default=Path("data/draw1k/draw1k.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/draw1k/draw1k.manifest.json"))
    args = parser.parse_args()
    archive = urllib.request.urlopen(URL, timeout=60).read()
    digest = hashlib.sha256(archive).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise SystemExit(f"archive SHA-256 mismatch: expected {ARCHIVE_SHA256}, got {digest}")
    rows, metadata = normalize(archive)
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload)
    split_counts = Counter(row["split"] for row in rows)
    source_index_counts = Counter(row["source_index"] for row in rows)
    manifest = {
        "dataset": "DRAW-1K",
        "release": "0.7",
        "source_url": URL,
        "paper_url": "https://aclanthology.org/E17-1047/",
        "archive_sha256": digest,
        "normalized_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "records": len(rows),
        "distinct_source_indices": len(source_index_counts),
        "duplicate_source_indices": sorted(index for index, count in source_index_counts.items() if count > 1),
        "split_counts": dict(split_counts),
        "single_target_records": sum(len(row["gold_solutions"]) == 1 for row in rows),
        "two_target_records": sum(len(row["gold_solutions"]) == 2 for row in rows),
        "source_split_file_counts": metadata["split_source_counts"],
        "release_note": "The split files contain 600 train, 199 dev, and 200 test IDs. Source index 153934 is duplicated identically in draw.json, yielding 200 dev rows and 1000 rows total.",
        "license_note": "The public release README requests citation but does not state an explicit dataset license; verify redistribution terms before publishing data files.",
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    (args.out.parent / "SOURCE_README.txt").write_text(metadata["release_readme"])
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
