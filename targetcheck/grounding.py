from __future__ import annotations

from dataclasses import dataclass

import z3

from .compiler_z3 import UnsupportedExpression, compile_spec
from .determinacy import CheckResult, check_target_determinacy
from .modelspec import Constraint, ModelSpec


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    reason: str
    repaired_spec: ModelSpec | None = None
    determinacy: CheckResult | None = None


def validate_repair(
    problem_text: str,
    spec: ModelSpec,
    candidate: Constraint,
    timeout_ms: int = 5_000,
) -> GateResult:
    if candidate.provenance == "EXPLICIT_TEXT":
        if not candidate.source_span or candidate.source_span not in problem_text:
            return GateResult(False, "source span is not an exact substring of the problem")
    elif candidate.provenance != "DOMAIN_SEMANTICS":
        return GateResult(False, "unsupported or missing provenance")

    try:
        base = compile_spec(spec)
        candidate_spec = ModelSpec(spec.variables, (candidate,), spec.target, spec.metadata)
        compiled_candidate = compile_spec(candidate_spec)
    except UnsupportedExpression as exc:
        return GateResult(False, f"candidate is not supported: {exc}")

    consistency = z3.Solver()
    consistency.set(timeout=timeout_ms)
    consistency.add(*base.assertions, *compiled_candidate.assertions)
    if consistency.check() != z3.sat:
        return GateResult(False, "candidate is inconsistent or solver returned unknown")

    redundancy = z3.Solver()
    redundancy.set(timeout=timeout_ms)
    redundancy.add(*base.assertions, z3.Not(compiled_candidate.assertions[-1]))
    if redundancy.check() == z3.unsat:
        return GateResult(False, "candidate is redundant")

    repaired = ModelSpec(
        spec.variables,
        spec.constraints + (candidate,),
        spec.target,
        spec.metadata,
    )
    result = check_target_determinacy(repaired, timeout_ms=timeout_ms)
    return GateResult(True, "accepted", repaired, result)
