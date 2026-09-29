from scripts.run_math500_natural import apply_repair
from targetcheck import Constraint, ModelSpec, Variable


def test_repair_normalizes_prose_provenance_when_quote_is_exact():
    problem = "If 4 daps = 7 yaps, and 5 yaps = 3 baps, how many daps equal 42 baps?"
    spec = ModelSpec(
        variables=(
            Variable("daps", "Int", lower=1),
            Variable("yaps", "Int", lower=1),
            Variable("baps", "Int", lower=1),
            Variable("answer", "Int"),
        ),
        constraints=(
            Constraint("c1", "4*daps == 7*yaps"),
            Constraint("c2", "5*yaps == 3*baps"),
        ),
        target="answer",
    )
    output = {
        "decision": "ADD_CONSTRAINT",
        "source_span": "  how many daps equal 42 baps?  ",
        "constraint": "answer*daps == 42*baps",
        "provenance": "The original problem states this relation.",
    }

    repaired, changed, reason = apply_repair(problem, spec, output)

    assert changed, reason
    assert repaired.constraints[-1].provenance == "EXPLICIT_TEXT"
    assert repaired.constraints[-1].source_span == "how many daps equal 42 baps?"


def test_repair_still_rejects_a_quote_not_found_in_problem():
    spec = ModelSpec(
        variables=(Variable("x", "Int"),),
        constraints=(),
        target="x",
    )
    output = {
        "decision": "ADD_CONSTRAINT",
        "source_span": "x equals five",
        "constraint": "x == 5",
        "provenance": "original problem",
    }

    _, changed, reason = apply_repair("Find x.", spec, output)

    assert not changed
    assert reason == "source span is not an exact substring of the problem"
