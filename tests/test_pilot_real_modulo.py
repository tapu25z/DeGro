from targetcheck.modelspec import Constraint, ModelSpec, Variable
from targetcheck.pilot import score


def test_real_modulo_candidate_is_scored_invalid_instead_of_crashing():
    row = {
        "label": "OMISSION",
        "problem": "The sum is 10.",
        "gold_target": 6,
        "spec": {
            "variables": [Variable("x", "Real").__dict__, Variable("y", "Real").__dict__],
            "constraints": [Constraint("c1", "x - y == 2").__dict__],
            "target": "x",
            "metadata": {},
        },
        "missing_constraint": Constraint("missing", "x + y == 10", "The sum is 10.", "EXPLICIT_TEXT").__dict__,
    }
    result = score(
        row,
        {"decision": "ADD_CONSTRAINT", "source_span": "The sum is 10.", "constraint": "x % 2 == 0"},
    )
    assert result["correct"] is False
    assert result["semantic_repair"] is False
