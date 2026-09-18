from scripts.run_draw1k_natural import answers_match, check_joint
from targetcheck.determinacy import CheckStatus


def raw_spec(constraints, targets=("x", "y")):
    return {
        "status": "SUPPORTED",
        "variables": [
            {"name": "x", "sort": "Real", "lower": None, "upper": None, "values": None},
            {"name": "y", "sort": "Real", "lower": None, "upper": None, "values": None},
        ],
        "constraints": [
            {"id": f"c{i}", "expression": expression, "source_span": "source", "provenance": "EXPLICIT_TEXT"}
            for i, expression in enumerate(constraints, 1)
        ],
        "targets": list(targets),
    }


def test_joint_determinacy_requires_the_unordered_pair_to_be_unique() -> None:
    result = check_joint(raw_spec(["x == 2"]))
    assert result.status == CheckStatus.AMBIGUOUS
    assert result.ambiguous_target in {"unordered target sum", "unordered target product"}


def test_joint_determinacy_accepts_a_unique_pair_up_to_permutation() -> None:
    result = check_joint(raw_spec(["(x == 2 and y == 3) or (x == 3 and y == 2)"]))
    assert result.status == CheckStatus.DETERMINATE
    assert answers_match(result.values, [2, 3])


def test_joint_determinacy_returns_all_values() -> None:
    result = check_joint(raw_spec(["x + y == 5", "x - y == 1"]))
    assert result.status == CheckStatus.DETERMINATE
    assert answers_match(result.values, [2.0, 3.0])


def test_draw_answers_are_order_invariant_and_tolerant() -> None:
    assert answers_match(("15/7", 3), [3.0, 2.14285714286])
    assert not answers_match(("15/7",), [3.0, 2.14285714286])
