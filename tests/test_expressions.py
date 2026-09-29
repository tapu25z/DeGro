import pytest

from targetcheck import Constraint, ModelSpec, Variable, check_target_determinacy, normalize_expression
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


def test_common_generated_boolean_and_power_syntax():
    normalized = normalize_expression("x > 0 && y^2 == 4", {"x", "y"})
    assert "and" in normalized
    assert "**" in normalized


def test_fractional_powers_and_root_functions_reach_z3():
    variables = (
        Variable("square_root", "Real"),
        Variable("cube_root", "Real"),
    )
    for square_expression, cube_expression in (
        ("64**0.5", "64**(1/3)"),
        ("sqrt(64)", "cbrt(64)"),
    ):
        spec = ModelSpec(
            variables,
            (
                Constraint("c1", f"square_root == {square_expression}"),
                Constraint("c2", f"cube_root == {cube_expression}"),
            ),
            "square_root - cube_root",
        )
        result = check_target_determinacy(spec)
        assert result.status == CheckStatus.DETERMINATE
        assert result.target_value == 4


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


def test_literal_integer_power_keeps_int_sort_for_modulo():
    spec = ModelSpec(
        variables=(Variable("u", "Int", lower=0, upper=9),),
        constraints=(Constraint("c1", "(18**6) % 10 == u"),),
        target="u",
    )

    result = check_target_determinacy(spec)

    assert result.status == CheckStatus.DETERMINATE
    assert result.target_value == 4


def test_finite_domain_combinators_for_logic_games():
    spec = ModelSpec(
        variables=(
            Variable("a", "Int", lower=1, upper=3),
            Variable("b", "Int", lower=1, upper=3),
            Variable("c", "Int", lower=1, upper=3),
            Variable("x", "Bool"),
            Variable("y", "Bool"),
            Variable("z", "Bool"),
        ),
        constraints=(
            Constraint("c1", "Distinct(a, b, c)"),
            Constraint("c2", "a < b"),
            Constraint("c3", "ExactlyOne(x, y, z)"),
            Constraint("c4", "AtMost(2, x, y, z)"),
            Constraint("c5", "AtLeast(1, x, y, z)"),
            Constraint("c6", "Sum([If(x, 1, 0), If(y, 1, 0), If(z, 1, 0)]) == 1"),
            Constraint("c7", "Count(x, y, z) == 1"),
        ),
        target="a < b",
    )

    result = check_target_determinacy(spec)

    assert result.status == CheckStatus.DETERMINATE
    assert result.target_value is True
