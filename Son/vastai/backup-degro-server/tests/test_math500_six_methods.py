from scripts.run_math500_six_methods import apply_grounded, apply_ungrounded, repair_prompt, resolve_source_span
from targetcheck import ModelSpec, Variable


def ambiguous_spec() -> ModelSpec:
    return ModelSpec((Variable("x", "Int", lower=0, upper=10),), (), "x")


def test_determinacy_only_and_degro_differ_in_prompt_not_acceptance_standard() -> None:
    spec = ambiguous_spec()
    det = repair_prompt("x is 6", spec, determinacy=True, grounding=False)
    degro = repair_prompt("x is 6", spec, determinacy=True, grounding=True)
    assert "not uniquely determined" in det and "not uniquely determined" in degro
    assert "exact contiguous quote that directly supports" not in det
    assert "exact contiguous quote that directly supports" in degro


def test_unsupported_answer_injection_fails_common_grounding_gate() -> None:
    output = {"decision": "ADD_CONSTRAINT", "source_span": None, "constraint": "x == 6", "provenance": "EXPLICIT_TEXT"}
    _, raw_changed, _, _ = apply_ungrounded(ambiguous_spec(), output)
    _, deployed_changed, _, _ = apply_grounded("How large is x?", ambiguous_spec(), output)
    assert raw_changed
    assert not deployed_changed


def test_whitespace_only_span_difference_is_resolved_to_source() -> None:
    problem = "After how many  seconds will both marks point north?"
    assert resolve_source_span(problem, "After how many seconds") == "After how many  seconds"
