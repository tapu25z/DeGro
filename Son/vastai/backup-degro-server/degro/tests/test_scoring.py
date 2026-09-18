from targetcheck.pilot import score


def omission_row() -> dict:
    return {
        "label": "OMISSION",
        "problem": "There are 10 tasks. A receives two more tasks than B. Find A.",
        "gold_target": 6,
        "spec": {
            "variables": [
                {"name": "a", "sort": "Int", "lower": 0},
                {"name": "b", "sort": "Int", "lower": 0},
            ],
            "constraints": [{"id": "c1", "expression": "a + b == 10"}],
            "target": "a",
        },
        "missing_constraint": {
            "id": "c_missing",
            "expression": "a == b + 2",
            "source_span": "A receives two more tasks than B.",
            "provenance": "EXPLICIT_TEXT",
        },
    }


def test_semantic_functional_and_grounded_repair_are_distinct():
    result = score(
        omission_row(),
        {
            "decision": "ADD_CONSTRAINT",
            "source_span": "A receives two more tasks than B.",
            "constraint": "2a == 2b + 4",
        },
    )

    assert result["semantic_repair"]
    assert result["functional_repair"]
    assert result["grounded_repair"]
    assert result["correct_repair"]
    assert not result["unsupported_repair"]
    assert result["correct"]


def test_forcing_gold_answer_is_functional_but_not_semantic_or_correct():
    result = score(
        omission_row(),
        {
            "decision": "ADD_CONSTRAINT",
            "source_span": "A receives two more tasks than B.",
            "constraint": "a == 6",
        },
    )

    assert result["functional_repair"]
    assert not result["semantic_repair"]
    assert not result["grounded_repair"]
    assert result["unsupported_repair"]
    assert not result["correct"]


def test_correct_equation_with_irrelevant_span_is_not_grounded():
    result = score(
        omission_row(),
        {
            "decision": "ADD_CONSTRAINT",
            "source_span": "There are 10 tasks.",
            "constraint": "a == b + 2",
        },
    )

    assert result["source_grounded"]
    assert result["semantic_repair"]
    assert result["functional_repair"]
    assert not result["grounded_repair"]
    assert result["unsupported_repair"]
    assert not result["correct"]


def test_any_added_constraint_is_unsupported_when_source_is_underspecified():
    row = omission_row()
    row["label"] = "UNDERSPECIFIED"
    row["problem"] = "There are 10 tasks. Find A."
    row["missing_constraint"] = None

    result = score(
        row,
        {
            "decision": "ADD_CONSTRAINT",
            "source_span": "There are 10 tasks.",
            "constraint": "a == 6",
        },
    )

    assert result["unsupported_repair"]
    assert not result["correct"]
