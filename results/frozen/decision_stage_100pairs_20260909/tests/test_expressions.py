import pytest

from targetcheck import Constraint, ModelSpec, Variable, normalize_expression
from targetcheck.compiler_z3 import UnsupportedExpression, compile_spec
from targetcheck.determinacy import CheckStatus
from targetcheck.grounding import validate_repair


def test_normalizes_implicit_multiplication_and_math_symbols():
    normalized = normalize_expression("−2x + 4(y + 1) ≤ 10", {"x", "y"})
    assert normalized == "-2 *x +4 *(y +1 )<=10 "


def test_normalizes_single_equals_for_mathematical_equations():
    assert normalize_expression("2x = 6", {"x"}) == "2 *x ==6 "


def test_does_not_guess_how_to_split_unknown_names():
    spec = ModelSpec(
        variables=(Variable("x", "Int"), Variable("y", "Int")),
        constraints=(Constraint("c1", "xy == 1"),),
        target="x",
    )
    with pytest.raises(UnsupportedExpression, match="unknown variable: xy"):
        compile_spec(spec)


def test_does_not_reinterpret_scientific_notation_as_a_variable_product():
    assert normalize_expression("2e01 + e01 == 21", {"e01"}) == "2e01 +e01 ==21 "


def test_grounded_repair_accepts_human_style_linear_equation():
    problem = "x + y = 10. -2x - y = -4. Find x."
    spec = ModelSpec(
        variables=(Variable("x", "Int"), Variable("y", "Int")),
        constraints=(Constraint("c1", "x + y == 10"),),
        target="x",
    )
    candidate = Constraint("c2", "-2x - y == -4", "-2x - y = -4", "EXPLICIT_TEXT")

    result = validate_repair(problem, spec, candidate)

    assert result.accepted
    assert result.determinacy is not None
    assert result.determinacy.status == CheckStatus.DETERMINATE
    assert result.determinacy.target_value == -6
