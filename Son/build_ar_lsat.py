#!/usr/bin/env python3
"""Flatten the official AR-LSAT game files into one JSONL row per question."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/ar_lsat/raw"
OUTPUT = ROOT / "data/ar_lsat"
SPLITS = {
    "train": RAW / "AR_TrainingData.json",
    "development": RAW / "AR_DevelopmentData.json",
    "test": RAW / "AR_TestData.json",
}
LABELS = "ABCDE"


def main() -> None:
    all_rows: list[dict[str, object]] = []
    skipped = Counter()
    for split, path in SPLITS.items():
        games = json.loads(path.read_text(encoding="utf-8"))
        rows: list[dict[str, object]] = []
        for game in games:
            for question in game["questions"]:
                options = question.get("options", [])
                if len(options) != 5:
                    skipped[f"{split}_non_five_option"] += 1
                    continue
                answer = str(question["answer"]).strip().upper()
                if answer not in LABELS:
                    skipped[f"{split}_bad_answer"] += 1
                    continue
                question_id = str(question["id"])
                game_id = str(game["id"])
                row = {
                    "unique_id": f"{split}/{game_id}/{question_id}",
                    "split": split,
                    "game_id": game_id,
                    "question_id": question_id,
                    "passage": game["passage"],
                    "question": question["question"],
                    "options": {label: option for label, option in zip(LABELS, options, strict=True)},
                    "answer": answer,
                }
                rows.append(row)
                all_rows.append(row)
        (OUTPUT / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        print(f"{split}: {len(rows)}")
    (OUTPUT / "all.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_rows),
        encoding="utf-8",
    )
    print(f"all: {len(all_rows)}")
    for reason, count in sorted(skipped.items()):
        print(f"{reason}: {count}")


if __name__ == "__main__":
    main()
