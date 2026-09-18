#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_heldout_mira import FAMILIES, _shuffle_source
from build_paired_mira import CODE_COMMIT, DATA_SHA256, DATA_URL, convert
from targetcheck.pilot import prompt_hash


SEED = 20270911
METHODS = ("self_review", "grounded_self_review", "nonunique", "nonunique_grounding")
MODELS = ("gpt-oss:20b", "gemma4:31b")


def main() -> None:
    raw = Path("data/mira_raw/family_types_20_50.jsonl")
    output = Path("data/paired/mira_confirmatory_remaining_120.jsonl")
    exclusions = (Path("data/paired/mira_pilot_80.jsonl"), Path("data/paired/mira_heldout_100.jsonl"))
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    if digest != DATA_SHA256:
        raise SystemExit(f"dataset checksum mismatch: {digest}")
    excluded_ids = {
        row["pair_id"]
        for path in exclusions
        for row in map(json.loads, path.read_text().splitlines())
    }
    rng = random.Random(SEED)
    pairs = []
    conversion_failures = Counter()
    for row in map(json.loads, raw.read_text().splitlines()):
        if row["family"] not in FAMILIES or row["id"] in excluded_ids:
            continue
        try:
            pair = convert(row)
        except (KeyError, StopIteration, ValueError) as exc:
            conversion_failures[type(exc).__name__] += 1
            continue
        if pair:
            pairs.append(_shuffle_source(pair, rng))
    rng.shuffle(pairs)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(case, separators=(",", ":")) + "\n"
        for pair in pairs
        for case in pair
    )
    output.write_text(content)
    manifest = {
        "study": "fresh confirmatory evaluation on every remaining solver-compatible MIRA-Math instance",
        "source_url": DATA_URL,
        "source_sha256": digest,
        "source_code_commit": CODE_COMMIT,
        "source_license": "CC BY 4.0",
        "selection_seed": SEED,
        "excluded_files": [str(path) for path in exclusions],
        "excluded_pair_count": len(excluded_ids),
        "families": list(FAMILIES),
        "family_counts": dict(Counter(pair[0]["family"] for pair in pairs)),
        "pairs": len(pairs),
        "cases": len(pairs) * 2,
        "methods": list(METHODS),
        "models": list(MODELS),
        "temperature": 1.0,
        "think": "medium",
        "primary_comparison": "FDA(nonunique_grounding) > FDA(grounded_self_review)",
        "analysis": "paired exact McNemar; Holm correction over the two model-specific primary tests",
        "prompt_hash": prompt_hash(),
        "conversion_failures": dict(conversion_failures),
        "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if len(pairs) != 120:
        raise SystemExit(f"expected all 120 remaining compatible pairs, found {len(pairs)}")


if __name__ == "__main__":
    main()
