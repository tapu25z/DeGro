from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorLabel(StrEnum):
    CORRECT = "CORRECT"
    MISSING_CONSTRAINT = "MISSING_CONSTRAINT"
    WRONG_CONSTRAINT = "WRONG_CONSTRAINT"
    EXTRA_CONSTRAINT = "EXTRA_CONSTRAINT"
    WRONG_DOMAIN = "WRONG_DOMAIN"
    WRONG_TARGET = "WRONG_TARGET"
    COMPUTATIONAL_ERROR = "COMPUTATIONAL_ERROR"
    OTHER = "OTHER"
    UNSURE = "UNSURE"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class NaturalErrorAnnotation:
    id: str
    primary_label: ErrorLabel
    target_critical_underformalization: bool
    evidence: str
    notes: str
    confidence: Confidence

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "NaturalErrorAnnotation":
        annotation = cls(
            id=str(raw.get("id", "")).strip(),
            primary_label=ErrorLabel(raw.get("primary_label")),
            target_critical_underformalization=raw.get("target_critical_underformalization"),
            evidence=str(raw.get("evidence", "")).strip(),
            notes=str(raw.get("notes", "")).strip(),
            confidence=Confidence(raw.get("confidence")),
        )
        annotation.validate()
        return annotation

    def validate(self) -> None:
        if not self.id:
            raise ValueError("annotation id must be non-empty")
        if not isinstance(self.target_critical_underformalization, bool):
            raise ValueError(f"{self.id}: target_critical_underformalization must be Boolean")
        if self.primary_label == ErrorLabel.MISSING_CONSTRAINT:
            if not self.target_critical_underformalization:
                raise ValueError(
                    f"{self.id}: MISSING_CONSTRAINT must be marked target-critical; "
                    "use OTHER when an omission cannot affect the requested target"
                )
        elif self.target_critical_underformalization:
            raise ValueError(
                f"{self.id}: only MISSING_CONSTRAINT may be a target-critical underformalization"
            )
        if self.primary_label not in {ErrorLabel.CORRECT, ErrorLabel.UNSURE} and not self.evidence:
            raise ValueError(f"{self.id}: an error label requires concise evidence")


def blank_annotation(item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "primary_label": "UNSURE",
        "target_critical_underformalization": False,
        "evidence": "",
        "notes": "",
        "confidence": "LOW",
    }
