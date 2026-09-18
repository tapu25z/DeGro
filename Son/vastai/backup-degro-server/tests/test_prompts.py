from targetcheck import Constraint, ModelSpec, Variable
from targetcheck.pilot import GROUNDING_RULE, METHODS, NONUNIQUE_VERDICT, build_prompt


def row() -> dict:
    spec = ModelSpec(
        variables=(Variable("a", "Int", lower=0), Variable("b", "Int", lower=0)),
        constraints=(Constraint("c1", "a + b == 10"),),
        target="a",
    )
    return {
        "pair_id": "test-pair",
        "problem": "There are 10 tasks. Find A.",
        "spec": {
            "variables": [variable.__dict__ for variable in spec.variables],
            "constraints": [constraint.__dict__ for constraint in spec.constraints],
            "target": spec.target,
        },
    }


def test_nonunique_grounding_is_a_registered_method():
    assert "nonunique_grounding" in METHODS


def test_grounded_self_review_has_grounding_without_solver_information():
    prompt = build_prompt("grounded_self_review", row())

    assert GROUNDING_RULE.strip() in prompt
    assert NONUNIQUE_VERDICT.strip() not in prompt
    assert "Witness A:" not in prompt
    assert "Witness B:" not in prompt


def test_nonunique_grounding_has_verdict_and_same_grounding_rule_without_witnesses():
    prompt = build_prompt("nonunique_grounding", row())

    assert NONUNIQUE_VERDICT.strip() in prompt
    assert GROUNDING_RULE.strip() in prompt
    assert "Witness A:" not in prompt
    assert "Witness B:" not in prompt


def test_targetcheck_uses_the_same_grounding_rule_with_target_witnesses():
    prompt = build_prompt("targetcheck", row())

    assert GROUNDING_RULE.strip() in prompt
    assert "Witness A:" in prompt
    assert "Witness B:" in prompt


def test_random_pair_does_not_claim_target_directed_selection():
    prompt = build_prompt("random_pair", row())

    assert "not selected based on the target" in prompt
    assert "Feasible assignment A:" in prompt
    assert "Target values:" not in prompt


def test_minimal_witness_is_marked_and_target_divergent():
    prompt = build_prompt("minimal_witness", row())

    assert "Witness selection: Minimal target-divergent." in prompt
    assert "Target values:" in prompt


def test_minimal_witness_grounding_combines_minimal_witness_and_grounding():
    prompt = build_prompt("minimal_witness_grounding", row())

    assert "Witness selection: Minimal target-divergent." in prompt
    assert "Target values:" in prompt
    assert GROUNDING_RULE.strip() in prompt
