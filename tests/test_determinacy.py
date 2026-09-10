from targetcheck import (
    Constraint,
    ModelSpec,
    Variable,
    check_minimal_target_determinacy,
    check_target_determinacy,
    find_feasible_pair,
)
from targetcheck.determinacy import CheckStatus
from targetcheck.grounding import validate_repair


def task_spec(*constraints: Constraint) -> ModelSpec:
    return ModelSpec(
        variables=(Variable("a", "Int", lower=0), Variable("b", "Int", lower=0)),
        constraints=constraints,
        target="a",
    )


def test_target_ambiguity_returns_divergent_witnesses():
    result = check_target_determinacy(task_spec(Constraint("c1", "a + b == 10")))
    assert result.status == CheckStatus.AMBIGUOUS
    assert result.witness_1["a"] != result.witness_2["a"]
    assert sum(result.witness_1.values()) == 10
    assert sum(result.witness_2.values()) == 10


def test_target_can_be_determinate_with_multiple_models():
    spec = ModelSpec(
        variables=(Variable("x", "Int"), Variable("y", "Int", lower=0)),
        constraints=(Constraint("c1", "x == 5"),),
        target="x",
    )
    result = check_target_determinacy(spec)
    assert result.status == CheckStatus.DETERMINATE
    assert result.target_value == 5


def test_literal_division_uses_exact_mathematical_rationals():
    spec = ModelSpec(
        variables=(Variable("x", "Real"),),
        constraints=(Constraint("c1", "x == (-5) / (-3)"),),
        target="x",
    )
    result = check_target_determinacy(spec)
    assert result.status == CheckStatus.DETERMINATE
    assert result.target_value == "5/3"


def test_inconsistent_is_not_reported_as_determinate():
    spec = task_spec(Constraint("c1", "a == 1"), Constraint("c2", "a == 2"))
    assert check_target_determinacy(spec).status == CheckStatus.INCONSISTENT


def test_grounded_repair_restores_determinacy():
    problem = "There are 10 tasks. A receives two more tasks than B. Find A."
    spec = task_spec(Constraint("c1", "a + b == 10"))
    candidate = Constraint(
        "c2",
        "a == b + 2",
        "A receives two more tasks than B.",
        "EXPLICIT_TEXT",
    )
    result = validate_repair(problem, spec, candidate)
    assert result.accepted
    assert result.determinacy.status == CheckStatus.DETERMINATE
    assert result.determinacy.target_value == 6


def test_ungrounded_repair_is_rejected():
    problem = "There are 10 tasks. Find A."
    spec = task_spec(Constraint("c1", "a + b == 10"))
    candidate = Constraint("c2", "a == b + 2", "A gets two more.", "EXPLICIT_TEXT")
    result = validate_repair(problem, spec, candidate)
    assert not result.accepted


def test_minimal_witness_changes_the_fewest_variables():
    spec = ModelSpec(
        variables=(Variable("x", "Int"), Variable("y", "Int"), Variable("z", "Int")),
        constraints=(Constraint("c1", "x + y == 10"),),
        target="x",
    )

    result = check_minimal_target_determinacy(spec)

    assert result.status == CheckStatus.AMBIGUOUS
    changed = [name for name in ("x", "y", "z") if result.witness_1[name] != result.witness_2[name]]
    assert set(changed) == {"x", "y"}
    assert result.witness_1["z"] == result.witness_2["z"]


def test_random_pair_returns_distinct_feasible_assignments():
    result = find_feasible_pair(task_spec(Constraint("c1", "a + b == 10")), random_seed=7)

    assert result.status == CheckStatus.AMBIGUOUS
    assert result.witness_1 != result.witness_2
    assert sum(result.witness_1.values()) == 10
    assert sum(result.witness_2.values()) == 10
