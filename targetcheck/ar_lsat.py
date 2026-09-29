from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import z3

from .compiler_z3 import UnsupportedExpression, compile_spec
from .modelspec import Constraint, ModelSpec


QuestionType = Literal[
    "COULD_TRUE",
    "MUST_TRUE",
    "CANNOT_TRUE",
    "COULD_FALSE",
    "MAXIMUM",
    "MINIMUM",
]


@dataclass(frozen=True)
class OptionCheck:
    label: str
    expression: str
    positive: str
    negative: str
    rank: int | None = None


@dataclass(frozen=True)
class ARCheckResult:
    status: str
    answer: str | None
    candidates: tuple[str, ...]
    base_status: str
    options: tuple[OptionCheck, ...]
    reason: str | None = None


def model_spec_from_ar(raw: dict[str, Any]) -> ModelSpec:
    return ModelSpec.from_dict(
        {
            "variables": raw["variables"],
            "constraints": raw["constraints"],
            "target": "0",
        }
    )


def _solver_status(spec: ModelSpec, timeout_ms: int) -> str:
    compiled = compile_spec(spec)
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.add(*compiled.assertions)
    result = solver.check()
    if result == z3.sat:
        return "SAT"
    if result == z3.unsat:
        return "UNSAT"
    return "UNKNOWN"


def check_ar_options(raw: dict[str, Any], timeout_ms: int = 5_000) -> ARCheckResult:
    try:
        base = model_spec_from_ar(raw)
        base_status = _solver_status(base, timeout_ms)
    except (KeyError, TypeError, AttributeError, UnsupportedExpression, z3.Z3Exception) as exc:
        return ARCheckResult("NOT_SUPPORTED", None, (), "ERROR", (), str(exc))
    if base_status != "SAT":
        return ARCheckResult(
            "BASE_INCONSISTENT" if base_status == "UNSAT" else "UNKNOWN",
            None,
            (),
            base_status,
            (),
            "base constraints are not satisfiable" if base_status == "UNSAT" else "solver returned unknown",
        )

    option_checks: list[OptionCheck] = []
    try:
        for option in raw["options"]:
            label = str(option["label"])
            expression = str(option["expression"])
            rank = option.get("rank")
            positive_spec = ModelSpec(
                base.variables,
                base.constraints + (Constraint(f"option_{label}", expression),),
                "0",
            )
            negative_spec = ModelSpec(
                base.variables,
                base.constraints + (Constraint(f"option_not_{label}", f"Not({expression})"),),
                "0",
            )
            option_checks.append(
                OptionCheck(
                    label,
                    expression,
                    _solver_status(positive_spec, timeout_ms),
                    _solver_status(negative_spec, timeout_ms),
                    int(rank) if rank is not None else None,
                )
            )
    except (KeyError, TypeError, AttributeError, ValueError, UnsupportedExpression, z3.Z3Exception) as exc:
        return ARCheckResult("NOT_SUPPORTED", None, (), base_status, tuple(option_checks), str(exc))

    if any(check.positive == "UNKNOWN" or check.negative == "UNKNOWN" for check in option_checks):
        return ARCheckResult("UNKNOWN", None, (), base_status, tuple(option_checks), "option check returned unknown")

    question_type: QuestionType = raw["question_type"]
    if question_type == "COULD_TRUE":
        candidates = [check.label for check in option_checks if check.positive == "SAT"]
    elif question_type in {"CANNOT_TRUE"}:
        candidates = [check.label for check in option_checks if check.positive == "UNSAT"]
    elif question_type == "MUST_TRUE":
        candidates = [check.label for check in option_checks if check.negative == "UNSAT"]
    elif question_type == "COULD_FALSE":
        candidates = [check.label for check in option_checks if check.negative == "SAT"]
    elif question_type in {"MAXIMUM", "MINIMUM"}:
        feasible = [check for check in option_checks if check.positive == "SAT" and check.rank is not None]
        if not feasible or len(feasible) != sum(check.positive == "SAT" for check in option_checks):
            return ARCheckResult(
                "NOT_SUPPORTED", None, (), base_status, tuple(option_checks),
                "MAXIMUM/MINIMUM requires an integer rank on every feasible option",
            )
        best = (max if question_type == "MAXIMUM" else min)(check.rank for check in feasible)
        candidates = [check.label for check in feasible if check.rank == best]
    else:
        return ARCheckResult("NOT_SUPPORTED", None, (), base_status, tuple(option_checks), f"unknown question type: {question_type}")

    if len(candidates) == 1:
        return ARCheckResult("UNIQUE", candidates[0], tuple(candidates), base_status, tuple(option_checks))
    return ARCheckResult(
        "NO_OPTION" if not candidates else "MULTIPLE_OPTIONS",
        None,
        tuple(candidates),
        base_status,
        tuple(option_checks),
    )
