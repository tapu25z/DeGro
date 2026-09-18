from __future__ import annotations

import json

import pytest

from scripts.build_draw_paired import convert_row, review_row, write_jsonl
from scripts.finalize_draw_paired import finalize


def sample_row():
    return {
        "unique_id": "draw1k/example",
        "source_index": 42,
        "split": "train",
        "problem": "The sum of x and y is 10. x is 2 more than y. Find x.",
        "gold_equations": ["x+y=10", "x-y=2"],
        "gold_solutions": [6.0, 4.0],
        "gold_template": ["m+n=a", "m-n=b"],
        "alignment": [
            {"coeff": "a", "Value": 10.0, "TokenId": 7, "SentenceId": 0},
            {"coeff": "b", "Value": 2.0, "TokenId": 10, "SentenceId": 1},
        ],
    }


def test_convert_row_is_solver_verified_and_proposes_a_span():
    candidate, reason = convert_row(sample_row())
    assert reason == "eligible"
    assert candidate is not None
    assert candidate["solver_checks"]["full_status"] == "DETERMINATE"
    assert candidate["solver_checks"]["base_status"] == "AMBIGUOUS"
    assert candidate["span_proposal"]["source_span"] in candidate["original_problem"]


def test_finalize_requires_completed_human_review(tmp_path):
    candidate, _ = convert_row(sample_row())
    packet = tmp_path / "review.jsonl"
    write_jsonl(packet, [review_row(candidate)])
    with pytest.raises(ValueError, match="not reviewed"):
        finalize(packet, tmp_path / "frozen.jsonl")


def test_finalize_emits_paired_cases_for_approved_review(tmp_path):
    candidate, _ = convert_row(sample_row())
    reviewed = review_row(candidate)
    proposal = reviewed["span_proposal"]
    reviewed["review"] = {
        "status": "APPROVE",
        "reviewer": "test-reviewer",
        "source_span_exact": proposal["source_span"],
        "underspecified_problem": proposal["underspecified_problem"],
        "meaning_preserved_after_deletion": True,
        "notes": "checked",
    }
    packet = tmp_path / "review.jsonl"
    output = tmp_path / "frozen.jsonl"
    write_jsonl(packet, [reviewed])
    manifest = finalize(packet, output)
    cases = [json.loads(line) for line in output.read_text().splitlines()]
    assert manifest["pairs"] == 1
    assert [case["label"] for case in cases] == ["OMISSION", "UNDERSPECIFIED"]
    assert cases[0]["missing_constraint"]["source_span"] == proposal["source_span"]
    assert cases[1]["missing_constraint"] is None


def test_title_abbreviation_is_not_treated_as_a_sentence_boundary():
    row = sample_row()
    row.update(
        {
            "problem": "Mr. Lee has 10 coins. He has 2 more dimes than nickels. Find the counts.",
            "gold_equations": ["x+y=10", "x-y=2"],
            "gold_solutions": [6.0, 4.0],
            "alignment": [
                {"coeff": "a", "Value": 10.0, "TokenId": 3, "SentenceId": 0},
                {"coeff": "b", "Value": 2.0, "TokenId": 3, "SentenceId": 1},
            ],
        }
    )
    candidate, reason = convert_row(row)
    assert reason == "eligible"
    assert candidate["span_proposal"]["source_span"] == "Mr. Lee has 10 coins."
