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

try:
    from scripts.fetch_draw1k import ARCHIVE_SHA256, ROOT, URL
except ModuleNotFoundError:
    from fetch_draw1k import ARCHIVE_SHA256, ROOT, URL


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and normalize ALG514 from the official derivation release.")
    parser.add_argument("--out", type=Path, default=Path("data/alg514/alg514.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/alg514/alg514.manifest.json"))
    args = parser.parse_args()
    archive = urllib.request.urlopen(URL, timeout=60).read()
    digest = hashlib.sha256(archive).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise SystemExit(f"archive SHA-256 mismatch: expected {ARCHIVE_SHA256}, got {digest}")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        raw_rows = json.loads(bundle.read(ROOT + "kushman.json"))
        folds = [set(bundle.read(ROOT + f"kushman-fold-{index}.txt").decode().split()) for index in range(5)]
    occurrences: Counter[str] = Counter()
    rows = []
    for raw in raw_rows:
        source_id = str(raw["iIndex"])
        occurrences[source_id] += 1
        uid = f"alg514/{source_id}" if occurrences[source_id] == 1 else f"alg514/{source_id}-duplicate-{occurrences[source_id]}"
        memberships = [index for index, ids in enumerate(folds) if source_id in ids]
        if len(memberships) != 1:
            raise ValueError(f"ALG514 ID must occur in exactly one fold: {source_id}, folds={memberships}")
        rows.append({
            "unique_id": uid, "source_index": raw["iIndex"], "split": "all", "fold": memberships[0],
            "problem": raw["sQuestion"], "gold_equations": raw["lEquations"],
            "gold_solutions": raw["lSolutions"], "gold_template": raw["Template"],
            "alignment": raw["Alignment"], "equivalent_alignments": raw["Equiv"],
        })
    rows.sort(key=lambda row: row["source_index"])
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload)
    manifest = {
        "dataset": "ALG514", "release": "0.7", "source_url": URL,
        "original_paper_url": "https://aclanthology.org/P14-1026/",
        "derivation_release_paper_url": "https://aclanthology.org/E17-1047/",
        "archive_sha256": digest, "normalized_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "records": len(rows), "distinct_source_indices": len(occurrences),
        "fold_counts": dict(Counter(str(row["fold"]) for row in rows)),
        "single_target_records": sum(len(row["gold_solutions"]) == 1 for row in rows),
        "two_target_records": sum(len(row["gold_solutions"]) == 2 for row in rows),
        "license_note": "The public release README requests citation but does not state an explicit dataset license; verify redistribution terms before publishing data files.",
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
