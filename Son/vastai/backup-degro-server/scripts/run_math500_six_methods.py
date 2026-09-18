#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import time
from pathlib import Path
from typing import Any

import z3

try:
    from scripts.run_math500_natural import FORMALIZATION_SCHEMA, REPAIR_SCHEMA, formalization_prompt, parse_object
    from scripts.run_olympiadbench_symcode import boxed, is_correct, symcode_prompt
except ModuleNotFoundError:
    from run_math500_natural import FORMALIZATION_SCHEMA, REPAIR_SCHEMA, formalization_prompt, parse_object
    from run_olympiadbench_symcode import boxed, is_correct, symcode_prompt
from targetcheck.compiler_z3 import UnsupportedExpression, compile_spec
from targetcheck.determinacy import CheckResult, CheckStatus, check_target_determinacy
from targetcheck.grounding import validate_repair
from targetcheck.modelspec import Constraint, ModelSpec
from targetcheck.providers import OllamaCloudClient, load_api_keys
from targetcheck.symcode_full import execute_symcode_full, extract_python_code


METHODS = (
    "symcode",
    "symcode_plus",
    "structured_solver",
    "grounded_self_review",
    "determinacy_only",
    "degro",
)


def repair_prompt(problem: str, spec: ModelSpec, *, determinacy: bool, grounding: bool) -> str:
    constraints = "\n".join(f"- {constraint.expression}" for constraint in spec.constraints)
    verdict = "\nSolver verdict: the target is not uniquely determined by the current constraints.\n" if determinacy else ""
    grounding_rule = """
For ADD_CONSTRAINT, provenance must be EXPLICIT_TEXT and source_span must be an exact contiguous quote that directly supports the proposed constraint, or provenance may be DOMAIN_SEMANTICS only for a conventional mathematical domain rule and source_span must be null. Otherwise ABSTAIN.
""" if grounding else ""
    return f"""Audit this mathematical formalization.
Original problem:
{problem}

Current constraints:
{constraints}

Target: {spec.target}
{verdict}{grounding_rule}
Return exactly one JSON object. ADD_CONSTRAINT means the source contains a missing condition; include the supporting source text when proposing one. ABSTAIN means the source does not justify a missing condition. Add at most one missing constraint. Do not add a derived final answer or a merely plausible assumption.
The constraint must use Python-style syntax: ==, !=, <, <=, >, >=, +, -, *, /, %, **, and, or. Never use &&, ||, the symbol ∈, function calls, or prose such as "is an integer". Variable sorts already encode integer/real/Boolean domains.

ADD example:
{{"decision":"ADD_CONSTRAINT","source_span":"exact quote","constraint":"x == 3","provenance":"EXPLICIT_TEXT"}}
ABSTAIN example:
{{"decision":"ABSTAIN","source_span":null,"constraint":null,"provenance":null}}"""


def prompt_hash() -> str:
    payload = "\n".join((inspect.getsource(formalization_prompt), inspect.getsource(symcode_prompt), inspect.getsource(repair_prompt)))
    return hashlib.sha256(payload.encode()).hexdigest()


def answer_correct(value: Any, gold: str) -> bool:
    if value is None or isinstance(value, bool):
        return False
    return is_correct(boxed(str(value)), [gold])


def directly_pins_target(spec: ModelSpec, output: dict[str, Any]) -> bool:
    expression = str(output.get("constraint") or "")
    target = re.escape(spec.target.strip())
    return bool(re.match(rf"^\s*{target}\s*==\s*[-+]?\d", expression))


def response_metrics(response: dict[str, Any]) -> dict[str, Any]:
    return {
        field: response[field]
        for field in ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
        if field in response
    }


def candidate_from(output: dict[str, Any], *, grounded: bool) -> Constraint | None:
    if output.get("decision") != "ADD_CONSTRAINT" or not isinstance(output.get("constraint"), str):
        return None
    provenance = output.get("provenance")
    if grounded and provenance not in {"EXPLICIT_TEXT", "DOMAIN_SEMANTICS"}:
        return None
    if not grounded:
        provenance = "EXPLICIT_TEXT"
    return Constraint("repair", output["constraint"], output.get("source_span"), provenance)


def resolve_source_span(problem: str, span: str) -> str | None:
    if span in problem:
        return span
    words = span.split()
    if not words:
        return None
    match = re.search(r"\s+".join(re.escape(word) for word in words), problem)
    return match.group(0) if match else None


def apply_ungrounded(spec: ModelSpec, output: dict[str, Any], timeout_ms: int = 5_000) -> tuple[ModelSpec, bool, str, CheckResult]:
    candidate = candidate_from(output, grounded=False)
    initial = check_target_determinacy(spec, timeout_ms=timeout_ms)
    if candidate is None:
        return spec, False, "abstain_or_malformed", initial
    try:
        base = compile_spec(spec)
        candidate_only = compile_spec(ModelSpec(spec.variables, (candidate,), spec.target, spec.metadata))
    except UnsupportedExpression as exc:
        return spec, False, f"unsupported: {exc}", initial
    consistency = z3.Solver()
    consistency.set(timeout=timeout_ms)
    consistency.add(*base.assertions, *candidate_only.assertions)
    if consistency.check() != z3.sat:
        return spec, False, "inconsistent_or_unknown", initial
    redundancy = z3.Solver()
    redundancy.set(timeout=timeout_ms)
    redundancy.add(*base.assertions, z3.Not(candidate_only.assertions[-1]))
    if redundancy.check() == z3.unsat:
        return spec, False, "redundant", initial
    repaired = ModelSpec(spec.variables, spec.constraints + (candidate,), spec.target, spec.metadata)
    result = check_target_determinacy(repaired, timeout_ms=timeout_ms)
    return repaired, True, "accepted", result


def apply_grounded(problem: str, spec: ModelSpec, output: dict[str, Any]) -> tuple[ModelSpec, bool, str, CheckResult]:
    initial = check_target_determinacy(spec)
    candidate = candidate_from(output, grounded=True)
    if candidate is None:
        return spec, False, "abstain_or_malformed", initial
    if candidate.provenance == "EXPLICIT_TEXT" and not isinstance(candidate.source_span, str):
        return spec, False, "missing_source_span", initial
    if candidate.provenance == "EXPLICIT_TEXT":
        resolved_span = resolve_source_span(problem, candidate.source_span)
        if resolved_span is None:
            return spec, False, "source_span_not_found", initial
        candidate = Constraint(candidate.id, candidate.expression, resolved_span, candidate.provenance)
    if candidate.provenance == "DOMAIN_SEMANTICS" and candidate.source_span is not None:
        return spec, False, "domain_semantics_has_span", initial
    gate = validate_repair(problem, spec, candidate)
    if not gate.accepted or gate.repaired_spec is None or gate.determinacy is None:
        return spec, False, gate.reason, initial
    return gate.repaired_spec, True, gate.reason, gate.determinacy


def completed_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    completed = set()
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
            if row.get("status") != "error":
                completed.add((row["id"], row["method"]))
        except (json.JSONDecodeError, KeyError):
            pass
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/math500/test.jsonl"))
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only-id", action="append", default=[])
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int)
    parser.add_argument("--accounts-per-worker", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--debug-attempts", type=int, default=2)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.data.read_text().splitlines()]
    if args.only_id:
        selected = set(args.only_id)
        rows = [row for row in rows if row["unique_id"] in selected]
    if args.limit is not None:
        rows = rows[: args.limit]
    rows = [row for index, row in enumerate(rows) if index % args.num_shards == args.shard_index]
    done = completed_keys(args.out)
    keys = load_api_keys(args.keys)
    offset = (args.account_offset if args.account_offset is not None else args.shard_index) % len(keys)
    rotated = keys[offset:] + keys[:offset]
    client = OllamaCloudClient(rotated[: min(args.accounts_per_worker, len(rotated))], timeout_s=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    config = {"model": args.model, "think": args.think, "temperature": 0.0, "prompt_hash": prompt_hash()}

    def write(stream, row: dict[str, Any], method: str, **fields: Any) -> None:
        record = {
            **config, "id": row["unique_id"], "subject": row["subject"], "level": row["level"],
            "gold_answer": row["answer"], "method": method, **fields,
        }
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()

    with args.out.open("a") as stream:
        for item_index, row in enumerate(rows, 1):
            uid, problem, gold = row["unique_id"], row["problem"], row["answer"]
            pending = {method for method in args.methods if (uid, method) not in done}
            if not pending:
                continue
            started = time.monotonic()

            sym_pending = pending & {"symcode", "symcode_plus"}
            if sym_pending:
                messages = [{"role": "user", "content": symcode_prompt(problem)}]
                attempts: list[dict[str, Any]] = []
                for attempt_index in range(args.debug_attempts + 1):
                    raw = ""
                    try:
                        response = client.chat(args.model, messages, options={"temperature": 0.0}, think=args.think)
                        raw = str(response.get("message", {}).get("content", ""))
                        code = extract_python_code(raw)
                        output = execute_symcode_full(code)
                        attempts.append({"status": "ok", "raw": raw, "code": code, "output": output, **response_metrics(response)})
                        break
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {str(exc)[:600]}"
                        attempts.append({"status": "error", "raw": raw, "error": error})
                        if attempt_index < args.debug_attempts:
                            messages.extend([
                                {"role": "assistant", "content": raw},
                                {"role": "user", "content": f"Debug the code based on this execution error. Return one corrected Python code block only.\n{error}"},
                            ])
                first, final = attempts[0], attempts[-1]
                if "symcode" in sym_pending:
                    first_network_error = first["status"] == "error" and "OllamaCloudError" in first.get("error", "")
                    write(stream, row, "symcode", status="error" if first_network_error else "ok", executed=first["status"] == "ok", answer=first.get("output"), correct=first["status"] == "ok" and is_correct(boxed(first.get("output", "")), [gold]), attempts=[first])
                if "symcode_plus" in sym_pending:
                    all_network_errors = all(attempt["status"] == "error" and "OllamaCloudError" in attempt.get("error", "") for attempt in attempts)
                    write(stream, row, "symcode_plus", status="error" if all_network_errors else "ok", executed=final["status"] == "ok", answer=final.get("output"), correct=final["status"] == "ok" and is_correct(boxed(final.get("output", "")), [gold]), attempts=attempts, debug_activated=len(attempts) > 1)

            structured_pending = pending & {"structured_solver", "grounded_self_review", "determinacy_only", "degro"}
            if structured_pending:
                raw_content = ""
                try:
                    response = client.chat(args.model, [{"role": "user", "content": formalization_prompt(problem)}], format_schema=FORMALIZATION_SCHEMA, options={"temperature": 0.0}, think=args.think)
                    raw_content = str(response.get("message", {}).get("content", ""))
                    raw_spec = parse_object(raw_content)
                    formalization_metrics = response_metrics(response)
                    if raw_spec.get("status") != "SUPPORTED":
                        for method in structured_pending:
                            write(stream, row, method, status="not_supported", correct=False, formalization=raw_spec, formalization_metrics=formalization_metrics)
                    else:
                        spec = ModelSpec.from_dict(raw_spec)
                        initial = check_target_determinacy(spec)
                        initial_fields = {
                            "initial_verdict": initial.status.value,
                            "initial_value": initial.target_value,
                            "formalization": raw_spec,
                            "formalization_metrics": formalization_metrics,
                        }
                        if "structured_solver" in structured_pending:
                            write(stream, row, "structured_solver", status="ok", verdict=initial.status.value, answer=initial.target_value, correct=initial.status == CheckStatus.DETERMINATE and answer_correct(initial.target_value, gold), **initial_fields)

                        for method in ("grounded_self_review", "determinacy_only", "degro"):
                            if method not in structured_pending:
                                continue
                            if method in {"determinacy_only", "degro"} and initial.status != CheckStatus.AMBIGUOUS:
                                write(stream, row, method, status="ok", triggered=False, changed=False, reason="not_triggered", verdict=initial.status.value, answer=initial.target_value, correct=initial.status == CheckStatus.DETERMINATE and answer_correct(initial.target_value, gold), **initial_fields)
                                continue
                            grounded = method != "determinacy_only"
                            response = client.chat(
                                args.model,
                                [{"role": "user", "content": repair_prompt(problem, spec, determinacy=method in {"determinacy_only", "degro"}, grounding=grounded)}],
                                format_schema=REPAIR_SCHEMA,
                                options={"temperature": 0.0},
                                think=args.think,
                            )
                            repair_raw = parse_object(str(response.get("message", {}).get("content", "")))
                            if grounded:
                                _, changed, reason, result = apply_grounded(problem, spec, repair_raw)
                                raw_changed, raw_reason, raw_result = changed, reason, result
                            else:
                                _, raw_changed, raw_reason, raw_result = apply_ungrounded(spec, repair_raw)
                                # The policy does not receive the explicit grounding rule,
                                # but every method is judged by the same deployment gate.
                                _, changed, reason, result = apply_grounded(problem, spec, repair_raw)
                            raw_correct = raw_result.status == CheckStatus.DETERMINATE and answer_correct(raw_result.target_value, gold)
                            correct = result.status == CheckStatus.DETERMINATE and answer_correct(result.target_value, gold)
                            write(stream, row, method, status="ok", triggered=True, changed=changed, grounded_valid=changed, direct_target_pin=directly_pins_target(spec, repair_raw), reason=reason, repair=repair_raw, repair_metrics=response_metrics(response), verdict=result.status.value, answer=result.target_value, raw_changed=raw_changed, raw_reason=raw_reason, raw_verdict=raw_result.status.value, raw_answer=raw_result.target_value, raw_correct=raw_correct, correct=correct, **initial_fields)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {str(exc)[:600]}"
                    for method in structured_pending:
                        if (uid, method) not in completed_keys(args.out):
                            write(stream, row, method, status="error", error=error, raw_content=raw_content[:3000], correct=False)

            elapsed = round(time.monotonic() - started, 1)
            print(f"[{item_index}/{len(rows)}] {uid} pending={len(pending)} elapsed={elapsed}s", flush=True)


if __name__ == "__main__":
    main()
