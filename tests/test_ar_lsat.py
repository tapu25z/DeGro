from targetcheck.ar_lsat import check_ar_options


def ordering_spec(question_type: str, options: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "SUPPORTED",
        "variables": [
            {"name": name, "sort": "Int", "lower": 1, "upper": 3, "values": None}
            for name in ("a", "b", "c")
        ],
        "constraints": [
            {"id": "c1", "expression": "Distinct(a, b, c)"},
            {"id": "c2", "expression": "a < b"},
            {"id": "c3", "expression": "b < c"},
        ],
        "question_type": question_type,
        "options": options,
    }


def test_ar_lsat_could_true_selects_only_satisfiable_option():
    result = check_ar_options(
        ordering_spec(
            "COULD_TRUE",
            [
                {"label": "A", "expression": "a == 3", "rank": None},
                {"label": "B", "expression": "b == 2", "rank": None},
                {"label": "C", "expression": "c == 1", "rank": None},
            ],
        )
    )

    assert result.status == "UNIQUE"
    assert result.answer == "B"


def test_ar_lsat_must_true_uses_unsat_negation():
    result = check_ar_options(
        ordering_spec(
            "MUST_TRUE",
            [
                {"label": "A", "expression": "a == 1", "rank": None},
                {"label": "B", "expression": "a < c", "rank": None},
                {"label": "C", "expression": "b == 3", "rank": None},
            ],
        )
    )

    # A and B are both logically necessary in this tiny example, so the
    # checker must report non-uniqueness rather than silently picking one.
    assert result.status == "MULTIPLE_OPTIONS"
    assert result.candidates == ("A", "B")


def test_ar_lsat_maximum_chooses_highest_satisfiable_rank():
    result = check_ar_options(
        ordering_spec(
            "MAXIMUM",
            [
                {"label": "A", "expression": "b == 1", "rank": 1},
                {"label": "B", "expression": "b == 2", "rank": 2},
                {"label": "C", "expression": "b == 3", "rank": 3},
            ],
        )
    )

    assert result.status == "UNIQUE"
    assert result.answer == "B"
