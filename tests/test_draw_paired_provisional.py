from __future__ import annotations

import json

from scripts.build_draw_paired import convert_row, write_jsonl
from scripts.materialize_draw_paired_provisional import materialize


def _candidate(index: int, split: str):
    row = {
        "unique_id": f"draw1k/{index}",
        "source_index": index,
        "split": split,
        "problem": f"The sum of x and y is {10 + index}. x is 2 more than y. Find x.",
        "gold_equations": [f"x+y={10 + index}", "x-y=2"],
        "gold_solutions": [(12 + index) / 2, (8 + index) / 2],
        "gold_template": ["m+n=a", "m-n=b"],
        "alignment": [
            {"coeff": "a", "Value": float(10 + index), "TokenId": 7, "SentenceId": 0},
            {"coeff": "b", "Value": 2.0, "TokenId": 3, "SentenceId": 1},
        ],
    }
    candidate, reason = convert_row(row)
    assert reason == "eligible"
    assert candidate is not None and not candidate["span_proposal"]["flags"]
    return candidate


def test_materialize_provisional_is_paired_stratified_and_oracle_valid(tmp_path):
    candidates = [_candidate(index, "train" if index < 3 else "dev") for index in range(5)]
    source = tmp_path / "candidates.jsonl"
    output = tmp_path / "provisional.jsonl"
    write_jsonl(source, candidates)
    manifest = materialize(source, output, pairs=4, seed=7)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert manifest["pairs"] == 4
    assert manifest["oracle_score_checks"] == 8
    assert len(rows) == 8
    assert all(row["dataset_stage"] == "PROVISIONAL_AWAITING_HUMAN_REVIEW" for row in rows)
