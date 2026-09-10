import pytest

from scripts.adjudicate_natural_errors import cohen_kappa
from scripts.analyze_natural_error_study import mcnemar_exact, proportion
from scripts.preannotate_natural_errors import parse_proposal
from targetcheck.error_taxonomy import NaturalErrorAnnotation


def annotation(**overrides):
    row = {
        "id": "item-1",
        "primary_label": "CORRECT",
        "target_critical_underformalization": False,
        "evidence": "",
        "notes": "",
        "confidence": "HIGH",
    }
    row.update(overrides)
    return row


def test_missing_constraint_must_be_target_critical_and_evidenced() -> None:
    with pytest.raises(ValueError, match="target-critical"):
        NaturalErrorAnnotation.from_dict(annotation(primary_label="MISSING_CONSTRAINT"))
    parsed = NaturalErrorAnnotation.from_dict(annotation(
        primary_label="MISSING_CONSTRAINT",
        target_critical_underformalization=True,
        evidence="The generated model omits the stated total.",
    ))
    assert parsed.target_critical_underformalization


def test_non_missing_label_cannot_enter_primary_subset() -> None:
    with pytest.raises(ValueError, match="only MISSING_CONSTRAINT"):
        NaturalErrorAnnotation.from_dict(annotation(
            primary_label="WRONG_TARGET",
            target_critical_underformalization=True,
            evidence="The requested variable differs from the target.",
        ))


def test_statistics_cover_perfect_agreement_and_exact_mcnemar() -> None:
    assert cohen_kappa(["A", "B", "A"], ["A", "B", "A"]) == 1.0
    assert mcnemar_exact(0, 3) == 0.25
    estimate = proportion(3, 4)
    assert estimate["rate"] == 0.75
    assert estimate["wilson_95_ci"][0] < 0.75 < estimate["wilson_95_ci"][1]


def test_ai_proposal_repairs_latex_escaping_and_routes_inconsistency_to_review() -> None:
    raw = r'{"primary_label":"MISSING_CONSTRAINT","target_critical_underformalization":false,"evidence":"missing \sqrt domain","notes":"","confidence":"HIGH"}'
    proposal, changes = parse_proposal(raw)
    assert proposal["target_critical_underformalization"] is True
    assert proposal["confidence"] == "LOW"
    assert "escaped_invalid_json_backslashes" in changes
    assert "aligned_primary_subset_boolean_with_label" in changes
