#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from build_paired_mira import CODE_COMMIT, DATA_SHA256, DATA_URL, convert


FAMILIES = (
    "linear_system_separator",
    "graph_path_sums",
    "crt_reconstruction",
    "rankdef_linear_shared",
    "moment_problem",
)
DEFAULT_DIFFICULTY_QUOTAS = {1: 5, 2: 7, 3: 8}


def _source_sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith(".") else text + "."


def _shuffle_source(pair: tuple[dict, dict], rng: random.Random) -> tuple[dict, dict]:
    omission, underspecified = pair
    base_sentences = [
        _source_sentence(constraint["source_span"])
        for constraint in omission["spec"]["constraints"]
    ]
    rng.shuffle(base_sentences)
    missing_sentence = _source_sentence(omission["missing_constraint"]["source_span"])
    insertion = rng.randrange(len(base_sentences) + 1)
    omission_sentences = list(base_sentences)
    omission_sentences.insert(insertion, missing_sentence)
    question = f"Find the integer value of {omission['spec']['target']}."
    return (
        {**omission, "problem": " ".join((*omission_sentences, question))},
        {**underspecified, "problem": " ".join((*base_sentences, question))},
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=Path("data/mira_raw/family_types_20_50.jsonl"))
    parser.add_argument("--exclude", type=Path, default=Path("data/paired/mira_pilot_80.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/paired/mira_heldout_100.jsonl"))
    parser.add_argument("--seed", type=int, default=20270910)
    args = parser.parse_args()

    digest = hashlib.sha256(args.raw.read_bytes()).hexdigest()
    if digest != DATA_SHA256:
        raise SystemExit(f"dataset checksum mismatch: {digest}")
    excluded_rows = [json.loads(line) for line in args.exclude.read_text().splitlines()]
    excluded_ids = {row["pair_id"] for row in excluded_rows}

    buckets: dict[str, dict[int, list[tuple[dict, dict]]]] = defaultdict(lambda: defaultdict(list))
    for line in args.raw.read_text().splitlines():
        row = json.loads(line)
        if row["family"] not in FAMILIES or row["id"] in excluded_ids:
            continue
        try:
            pair = convert(row)
        except (KeyError, StopIteration, ValueError):
            continue
        if pair:
            buckets[row["family"]][row["difficulty"]].append(pair)

    rng = random.Random(args.seed)
    selected: list[tuple[dict, dict]] = []
    for family in FAMILIES:
        quotas = {1: 20} if family == "crt_reconstruction" else DEFAULT_DIFFICULTY_QUOTAS
        for difficulty, quota in quotas.items():
            candidates = buckets[family][difficulty]
            rng.shuffle(candidates)
            if len(candidates) < quota:
                raise SystemExit(
                    f"only {len(candidates)} candidates for {family} difficulty {difficulty}; need {quota}"
                )
            selected.extend(_shuffle_source(pair, rng) for pair in candidates[:quota])
    rng.shuffle(selected)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as stream:
        for pair in selected:
            for case in pair:
                stream.write(json.dumps(case, separators=(",", ":")) + "\n")

    pair_counts = Counter(pair[0]["family"] for pair in selected)
    difficulty_counts = Counter(pair[0]["difficulty"] for pair in selected)
    manifest = {
        "source_url": DATA_URL,
        "source_sha256": digest,
        "source_code_commit": CODE_COMMIT,
        "source_license": "CC BY 4.0",
        "selection_seed": args.seed,
        "excluded_pairs_file": str(args.exclude),
        "excluded_pairs_sha256": hashlib.sha256(args.exclude.read_bytes()).hexdigest(),
        "source_order_randomized": True,
        "families": list(FAMILIES),
        "pair_counts": dict(pair_counts),
        "difficulty_counts": {str(key): value for key, value in sorted(difficulty_counts.items())},
        "pairs": len(selected),
        "cases": len(selected) * 2,
        "output_sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
