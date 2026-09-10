from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import z3

from .compiler_z3 import UnsupportedExpression, compile_spec, model_value
from .modelspec import ModelSpec


class CheckStatus(StrEnum):
    DETERMINATE = "DETERMINATE"
    AMBIGUOUS = "AMBIGUOUS"
    INCONSISTENT = "INCONSISTENT"
    UNKNOWN = "UNKNOWN"
    NOT_SUPPORTED = "NOT_SUPPORTED"


@dataclass(frozen=True)
class CheckResult:
    status: CheckStatus
    target_value: bool | int | str | None = None
    witness_1: dict[str, bool | int | str] | None = None
    witness_2: dict[str, bool | int | str] | None = None
    reason: str | None = None


def _assignment(compiled, model: z3.ModelRef) -> dict[str, bool | int | str]:
    return {name: model_value(model, symbol) for name, symbol in compiled.symbols.items()}


def check_target_determinacy(spec: ModelSpec, timeout_ms: int = 5_000) -> CheckResult:
    try:
        base = compile_spec(spec)
        first = compile_spec(spec, "__1")
        second = compile_spec(spec, "__2")
    except UnsupportedExpression as exc:
        return CheckResult(CheckStatus.NOT_SUPPORTED, reason=str(exc))

    feasibility = z3.Solver()
    feasibility.set(timeout=timeout_ms)
    feasibility.add(*base.assertions)
    base_status = feasibility.check()
    if base_status == z3.unsat:
        return CheckResult(CheckStatus.INCONSISTENT)
    if base_status == z3.unknown:
        return CheckResult(CheckStatus.UNKNOWN, reason=feasibility.reason_unknown())

    checker = z3.Solver()
    checker.set(timeout=timeout_ms)
    checker.add(*first.assertions, *second.assertions, first.target != second.target)
    status = checker.check()
    if status == z3.sat:
        model = checker.model()
        return CheckResult(
            CheckStatus.AMBIGUOUS,
            witness_1=_assignment(first, model),
            witness_2=_assignment(second, model),
        )
    if status == z3.unsat:
        model = feasibility.model()
        return CheckResult(
            CheckStatus.DETERMINATE,
            target_value=model_value(model, base.target),
        )
    return CheckResult(CheckStatus.UNKNOWN, reason=checker.reason_unknown())


def check_minimal_target_determinacy(spec: ModelSpec, timeout_ms: int = 5_000) -> CheckResult:
    """Return a target-divergent pair changing the fewest declared variables."""

    try:
        base = compile_spec(spec)
        first = compile_spec(spec, "__1")
        second = compile_spec(spec, "__2")
    except UnsupportedExpression as exc:
        return CheckResult(CheckStatus.NOT_SUPPORTED, reason=str(exc))

    feasibility = z3.Solver()
    feasibility.set(timeout=timeout_ms)
    feasibility.add(*base.assertions)
    base_status = feasibility.check()
    if base_status == z3.unsat:
        return CheckResult(CheckStatus.INCONSISTENT)
    if base_status == z3.unknown:
        return CheckResult(CheckStatus.UNKNOWN, reason=feasibility.reason_unknown())

    differences = [
        z3.If(first.symbols[name] != second.symbols[name], 1, 0)
        for name in first.symbols
    ]
    for maximum_changes in range(1, len(differences) + 1):
        checker = z3.Solver()
        checker.set(timeout=timeout_ms)
        checker.add(*first.assertions, *second.assertions, first.target != second.target)
        checker.add(z3.Sum(*differences) <= maximum_changes)
        status = checker.check()
        if status == z3.sat:
            model = checker.model()
            return CheckResult(
                CheckStatus.AMBIGUOUS,
                witness_1=_assignment(first, model),
                witness_2=_assignment(second, model),
            )
        if status == z3.unknown:
            return CheckResult(CheckStatus.UNKNOWN, reason=checker.reason_unknown())

    model = feasibility.model()
    return CheckResult(CheckStatus.DETERMINATE, target_value=model_value(model, base.target))


def find_feasible_pair(
    spec: ModelSpec,
    timeout_ms: int = 5_000,
    random_seed: int = 0,
) -> CheckResult:
    """Return two arbitrary distinct feasible assignments without targeting q."""

    try:
        compiled = compile_spec(spec)
    except UnsupportedExpression as exc:
        return CheckResult(CheckStatus.NOT_SUPPORTED, reason=str(exc))

    first_solver = z3.Solver()
    first_solver.set(timeout=timeout_ms, random_seed=random_seed)
    first_solver.add(*compiled.assertions)
    first_status = first_solver.check()
    if first_status == z3.unsat:
        return CheckResult(CheckStatus.INCONSISTENT)
    if first_status == z3.unknown:
        return CheckResult(CheckStatus.UNKNOWN, reason=first_solver.reason_unknown())
    first_model = first_solver.model()
    first_assignment = _assignment(compiled, first_model)

    second_solver = z3.Solver()
    second_solver.set(timeout=timeout_ms, random_seed=random_seed + 1)
    second_solver.add(*compiled.assertions)
    second_solver.add(z3.Or(*(
        symbol != first_model.eval(symbol, model_completion=True)
        for symbol in compiled.symbols.values()
    )))
    second_status = second_solver.check()
    if second_status == z3.sat:
        return CheckResult(
            CheckStatus.AMBIGUOUS,
            witness_1=first_assignment,
            witness_2=_assignment(compiled, second_solver.model()),
        )
    if second_status == z3.unsat:
        return CheckResult(
            CheckStatus.DETERMINATE,
            target_value=model_value(first_model, compiled.target),
            reason="the full satisfying assignment is unique",
        )
    return CheckResult(CheckStatus.UNKNOWN, reason=second_solver.reason_unknown())
