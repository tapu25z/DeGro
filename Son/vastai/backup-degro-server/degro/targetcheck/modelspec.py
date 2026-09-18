from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SortName = Literal["Int", "Real", "Bool"]
Provenance = Literal["EXPLICIT_TEXT", "DOMAIN_SEMANTICS"]


@dataclass(frozen=True)
class Variable:
    name: str
    sort: SortName
    lower: int | float | None = None
    upper: int | float | None = None
    values: tuple[int, ...] | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Variable":
        values = raw.get("values")
        return cls(
            name=raw["name"],
            sort=raw.get("sort", raw.get("domain", "Real")),
            lower=raw.get("lower"),
            upper=raw.get("upper"),
            values=tuple(values) if values is not None else None,
        )


@dataclass(frozen=True)
class Constraint:
    id: str
    expression: str
    source_span: str | None = None
    provenance: Provenance | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Constraint":
        return cls(
            id=raw["id"],
            expression=raw["expression"],
            source_span=raw.get("source_span"),
            provenance=raw.get("provenance"),
        )


@dataclass(frozen=True)
class ModelSpec:
    variables: tuple[Variable, ...]
    constraints: tuple[Constraint, ...]
    target: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ModelSpec":
        return cls(
            variables=tuple(Variable.from_dict(v) for v in raw["variables"]),
            constraints=tuple(Constraint.from_dict(c) for c in raw["constraints"]),
            target=raw["target"],
            metadata=dict(raw.get("metadata", {})),
        )
