#!/usr/bin/env python3
"""Run problem -> ModelSpec -> DeGro, without generated solution code.

Example:
    conda run --no-capture-output -n Degro python -u Son/run_degro_direct.py \
      --model gpt-oss:20b --workers 8
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_math500_natural import (  # noqa: E402
    REPAIR_SCHEMA,
    apply_repair,
    parse_object,
)
from scripts.run_math500_six_methods import answer_correct  # noqa: E402
from targetcheck import ModelSpec, check_target_determinacy  # noqa: E402
from targetcheck.determinacy import CheckResult, CheckStatus  # noqa: E402
from targetcheck.providers import OllamaCloudClient  # noqa: E402


PIPELINE_VERSION = "direct_spec_to_z3_v13_semantic_prompt"

FORMALIZATION_SYSTEM_PROMPT = """You are a meticulous mathematical modeler.
Translate the source problem into a semantically faithful ModelSpec, not merely
a satisfiable set of equations. Return JSON only.

Before answering, silently audit the model:
1. Define what every variable measures, including its unit and whether it is an
   Int, Real, count, length, rate, value, or coordinate.
2. Trace every number and relation in the source into the constraints. Preserve
   direction: transfers change both parties; "answered 80" means correct plus
   incorrect equals 80; "three items for $1" means items/3 dollars.
3. For equivalent unit bundles such as "4 A = 7 B", do not write
   4*A_count == 7*B_count. Counts representing the same value satisfy
   A_count/4 == B_count/7, equivalently 7*A_count == 4*B_count.
4. Use standard definitions exactly: a regular n-gon's exterior angle is 360/n;
   geometric lengths are positive when the object is nondegenerate; discrete
   counts such as numbers of sides are Int.
5. Do not precompute a large arithmetic fact and insert it as a constraint when
   it can be modeled directly. For a congruence, introduce an integer quotient
   and remainder so the solver performs the arithmetic.
6. Match the requested target exactly. "Product/sum of all solutions" is not one
   solution variable. Use coefficient identities such as Vieta when appropriate.
   Interval endpoints must be tied to boundary equalities, not just to one sample
   point inside the interval. Polynomial identities require coefficient matching.
7. Check every ratio for inversion, every denominator for nonzero conditions,
   and every requested transfer, total, complement, and rounding instruction.
8. Mentally substitute the constraints back into the original wording. If they
   describe a different story or a different target, rebuild the model.

Never add the known final answer as a constraint and never use the gold answer.
Use only the supported expression language supplied by the user prompt."""

REPAIR_SYSTEM_PROMPT = """Repair only with one condition stated or necessarily
implied by the original problem. Never invent a value, assumption, domain, or
equality to the answer. Diagnose the two witnesses first and add a constraint
that actually excludes the invalid witness; never return a redundant consequence
of the current ModelSpec. Counts are nonnegative, and weights, lengths, side
counts, denominators, and sizes are strictly positive when the named object is
necessarily nondegenerate.

Use a valid Z3-compatible expression. For EXPLICIT_TEXT, copy source_span
verbatim from the original problem, preserving every character, LaTeX command,
math delimiter, punctuation, capitalization, and internal whitespace. Verify
that it is an exact contiguous substring. Use DOMAIN_SEMANTICS only for a true
conventional domain rule and set source_span to null. If the target represents
the wrong quantity, several constraints are missing, or one grounded condition
cannot make the target determinate, return ABSTAIN. Return JSON only."""

FORMALIZATION_SCHEMA = {
    "type": "object",
    "properties": {
        "variables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sort": {"type": "string", "enum": ["Int", "Real", "Bool"]},
                    "lower": {"type": ["number", "null"]},
                    "upper": {"type": ["number", "null"]},
                    "values": {"type": ["array", "null"], "items": {"type": "integer"}},
                },
                "required": ["name", "sort", "lower", "upper", "values"],
                "additionalProperties": False,
            },
        },
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "expression": {"type": "string"},
                },
                "required": ["id", "expression"],
                "additionalProperties": False,
            },
        },
        "target": {"type": "string"},
    },
    "required": ["variables", "constraints", "target"],
    "additionalProperties": False,
}


def formalization_prompt(problem: str) -> str:
    return f"""Translate this problem directly into one Z3-compatible ModelSpec.
Problem:
{problem}

Return exactly one JSON object with variables, constraints, and target.
Do not include status, source_span, or provenance. Encode every target-relevant
condition in the problem, but do not solve the problem or add the final answer
as a constraint. Use Int/Real/Bool variables and a scalar target. Include
mathematical domain conditions implied by the objects: counts cannot be
negative, lengths and distances cannot be negative, every denominator must be
nonzero, and a positive ratio after removing items requires a positive
remaining count. Make the target exactly the quantity requested by the
question. When the question fixes one quantity (for example, asks how many A
equal 42 B), constrain B to that value and target A. Treat polynomial
equalities stated as identities by equating coefficients; do not encode them
as equality at one unconstrained sample point. Use ceil/floor explicitly when
rounding is required; `/` is exact arithmetic, including for Int variables.

Do not encode a derived arithmetic result unless it follows transparently from
the displayed constraints. Prefer equations that preserve the source numbers
and let Z3 derive the result. Before returning, verify that solving the ModelSpec
would answer the exact question rather than a related intermediate quantity.

Expressions use Python-style ==, !=, <, <=, >, >=, +, -, *, /, %, **,
and, or. Exponents may be integers or exact fractions such as **(1/2) and
**(1/3). sqrt(x), cbrt(x), ceil(x), ceiling(x), floor(x), abs(x), and Abs(x)
are also accepted. And(...), Or(...), Not(...), Implies(...), If(...),
Mod(a,b), ToReal(x), and ToInt(x) are accepted aliases. Do not use prose,
undeclared variables, quantifiers, or any other function inside expressions.

Example:
{{"variables":[{{"name":"x","sort":"Real","lower":null,"upper":null,"values":null}}],"constraints":[{{"id":"c1","expression":"2*x == 6"}}],"target":"x"}}"""


def formalization_correction_prompt(problem: str, raw_spec: dict[str, Any], reason: str) -> str:
    return f"""Discard and rebuild this invalid or inconsistent ModelSpec from
the original problem. Preserve the mathematical meaning. Do not solve the
problem and do not add its final answer as a constraint. Check unit direction,
bundle equivalences, exact division, transfers, totals, rounding, domains,
polynomial identities, and whether the target is exactly what was requested.

Problem:
{problem}

Rejected ModelSpec:
{json.dumps(raw_spec, ensure_ascii=False)}

Checker failure:
{reason}

Use only declared Int/Real/Bool variables; ==, !=, <, <=, >, >=, +, -, *, /,
%, **, and, or; sqrt, cbrt, ceil, floor, abs; And, Or, Not, Implies, If, Mod,
ToReal, and ToInt. Do not use pi, trigonometry, logarithms, quantifiers, lists,
comprehensions, subscripts, or calls to user-defined functions.
Return exactly one JSON object with variables, constraints, and target."""


def read_env(path: Path) -> tuple[dict[str, str], tuple[str, ...]]:
    settings: dict[str, str] = {}
    keys: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip("'\"")
            if name == "OLLAMA_HOST":
                settings[name] = value
            elif name == "OLLAMA_API_KEYS":
                keys.extend(part.strip() for part in value.split(",") if part.strip())
            elif name.startswith("OLLAMA_API_KEY") and value:
                keys.append(value)
        elif line:
            keys.append(line.split()[-1].strip("'\""))
    return settings, tuple(dict.fromkeys(keys))


def request_json(
    client: OllamaCloudClient,
    model: str,
    prompt: str,
    schema: dict[str, Any],
    think: str,
    system_prompt: str | None = None,
    *,
    temperature: float = 0.0,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            messages = []
            if system_prompt is not None:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt + ("\nReturn only JSON." if attempt else "")})
            response = client.chat(
                model,
                messages,
                format_schema=schema if attempt == 0 else None,
                options={"temperature": temperature},
                think=think,
            )
            return parse_object(str(response.get("message", {}).get("content", "")))
        except Exception as exc:
            last_error = exc
    raise ValueError(f"model did not return valid JSON: {last_error}")


def check_record(result: CheckResult) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "target_value": result.target_value,
        "witness_1": result.witness_1,
        "witness_2": result.witness_2,
        "reason": result.reason,
    }


def repair_prompt(problem: str, raw_spec: dict[str, Any], result: CheckResult) -> str:
    return f"""The target of this ModelSpec is ambiguous. Find at most one missing
constraint supported by the original problem, or abstain.

Original problem (copy source_span only from between these markers):
<BEGIN_ORIGINAL_PROBLEM>
{problem}
<END_ORIGINAL_PROBLEM>

Current ModelSpec:
{json.dumps(raw_spec, ensure_ascii=False)}

Two feasible assignments with different target values:
{json.dumps(result.witness_1, ensure_ascii=False)}
{json.dumps(result.witness_2, ensure_ascii=False)}

Return one JSON object with decision, source_span, constraint, and provenance.
For ADD_CONSTRAINT, use a Python-style arithmetic comparison; EXPLICIT_TEXT
requires source_span to be copied character-for-character from the original
problem. Preserve $, backslashes, LaTeX commands, punctuation, capitalization,
and whitespace. Do not paraphrase, normalize, simplify, or regenerate the quote.
Before returning, verify that source_span occurs verbatim between the markers.
Use provenance="EXPLICIT_TEXT" for a quoted condition. DOMAIN_SEMANTICS requires
source_span=null and is only for conventional mathematical domain rules, such
as a length or distance being nonnegative. A
compound constraint using And(...) is allowed when one sentence states several
parts of the same condition.
Use Python/Z3 `and` or And(...), never `&&`.
Do not add the computed answer or an unsupported assumption. If one condition
cannot determine the target, or if you cannot copy an exact supporting span,
return ABSTAIN.

ABSTAIN example: {{"decision":"ABSTAIN","source_span":null,"constraint":null,"provenance":null}}"""


def scalar_fraction(value: Any) -> Fraction | None:
    """Read the numeric answer formats used by the selected MATH-500 rows."""
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip().replace(r"\!", "").replace(r"\,", "")
    raw = raw.replace(r"\$", "").replace("$", "").replace(",", "")
    raw = re.sub(r"\\mbox\{[^}]*\}(?:\^\{?\d+\}?)?", "", raw)
    raw = raw.replace(r"^\circ", "").replace(r"\circ", "")
    raw = raw.replace(r"\dfrac", r"\frac").strip()
    mixed = re.fullmatch(r"([+-]?\d+)\s+\\frac\{(\d+)\}\{(\d+)\}", raw)
    if mixed:
        whole, numerator, denominator = map(int, mixed.groups())
        if denominator == 0:
            return None
        part = Fraction(numerator, denominator)
        return whole - part if whole < 0 else whole + part
    plain_mixed = re.fullmatch(r"([+-]?\d+)\s+(\d+)\s*/\s*(\d+)", raw)
    if plain_mixed:
        whole, numerator, denominator = map(int, plain_mixed.groups())
        if denominator == 0:
            return None
        part = Fraction(numerator, denominator)
        return whole - part if whole < 0 else whole + part
    fraction = re.fullmatch(r"\\frac\{([+-]?\d+)\}\{(\d+)\}", raw)
    if fraction:
        numerator, denominator = map(int, fraction.groups())
        return Fraction(numerator, denominator) if denominator else None
    short_fraction = re.fullmatch(r"\\frac\s*\{?([+-]?\d)\}?\s*\{?(\d)\}?", raw)
    if short_fraction:
        numerator, denominator = map(int, short_fraction.groups())
        return Fraction(numerator, denominator) if denominator else None
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:/\d+)?", raw):
        try:
            return Fraction(raw)
        except (ValueError, ZeroDivisionError):
            pass
    return None


def _latex_argument(source: str, index: int, *, one_digit: bool = False) -> tuple[str, int]:
    while index < len(source) and source[index].isspace():
        index += 1
    if index >= len(source):
        raise ValueError("missing LaTeX argument")
    if source[index] == "{":
        depth = 1
        end = index + 1
        while end < len(source) and depth:
            if source[end] == "{":
                depth += 1
            elif source[end] == "}":
                depth -= 1
            end += 1
        if depth:
            raise ValueError("unclosed LaTeX group")
        return source[index + 1:end - 1], end
    if source[index] == "\\":
        command_end = index + 1
        while command_end < len(source) and source[command_end].isalpha():
            command_end += 1
        command = source[index:command_end]
        if command in {r"\sqrt", r"\frac", r"\dfrac"}:
            expression, end = _latex_scalar_expression(source, index)
            return expression, end
        return command, command_end
    if one_digit and source[index].isdigit():
        return source[index], index + 1
    match = re.match(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", source[index:])
    if match:
        return match.group(0), index + len(match.group(0))
    return source[index], index + 1


def _latex_scalar_expression(source: str, index: int = 0) -> tuple[str, int]:
    output: list[str] = []
    while index < len(source):
        char = source[index]
        if char == "\\":
            end = index + 1
            while end < len(source) and source[end].isalpha():
                end += 1
            command = source[index:end]
            if command in {r"\frac", r"\dfrac"}:
                numerator, index = _latex_argument(source, end, one_digit=True)
                denominator, index = _latex_argument(source, index, one_digit=True)
                output.append(f"(({_latex_scalar_expression(numerator)[0]})/({_latex_scalar_expression(denominator)[0]}))")
                continue
            if command == r"\sqrt":
                degree = None
                if end < len(source) and source[end] == "[":
                    close = source.find("]", end + 1)
                    if close < 0:
                        raise ValueError("unclosed root degree")
                    degree = source[end + 1:close]
                    end = close + 1
                radicand, index = _latex_argument(source, end)
                inner = _latex_scalar_expression(radicand)[0]
                output.append(f"sqrt({inner})" if degree is None else f"root({inner},{degree})")
                continue
            if command == r"\pi":
                output.append("pi")
            elif command in {r"\cdot", r"\times"}:
                output.append("*")
            elif command in {r"\left", r"\right"}:
                index = end
                continue
            else:
                output.append(command[1:])
            index = end
            continue
        if char == "{":
            inner, index = _latex_argument(source, index)
            output.append(f"({_latex_scalar_expression(inner)[0]})")
            continue
        if char == "^":
            output.append("**")
        elif char == "\\":
            pass
        elif char in "}$":
            pass
        else:
            output.append(char)
        index += 1
    expression = "".join(output)
    expression = re.sub(r"(?<=\d)\s+(?=(?:sqrt|root|pi)\()", "*", expression)
    expression = re.sub(r"(?<=\d)(?=(?:sqrt|root|pi)\()", "*", expression)
    expression = re.sub(r"(?<=\))(?=\()", "*", expression)
    expression = re.sub(r"(?<=\d)\s+(?=\()", "*", expression)
    return expression, index


def scalar_approx(value: Any) -> float | None:
    fraction = scalar_fraction(value)
    if fraction is not None:
        return float(fraction)
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip().removesuffix("?")
    raw = raw.replace(r"\!", "").replace(r"\,", "").replace(",", "")
    raw = re.sub(r"\\(?:mbox|text)\{[^}]*\}(?:\^\{?\d+\}?)?", "", raw)
    raw = raw.replace(r"\$", "").replace("$", "")
    raw = raw.replace(r"^\circ", "").replace(r"\circ", "")
    raw = raw.replace(r"\left", "").replace(r"\right", "")
    # Direct-answer models commonly emit the Unicode radical glyph while the
    # dataset uses LaTeX. Normalize simple scalar radicals before SymPy parsing.
    raw = re.sub(r"√\s*\(([^()]+)\)", r"sqrt(\1)", raw)
    raw = re.sub(r"√\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", r"sqrt(\1)", raw)
    if raw.startswith(r"\boxed{") and raw.endswith("}"):
        raw = raw[7:-1]
    mixed = re.fullmatch(r"([+-]?\d+)\s+\\(?:d?frac)\{(\d+)\}\{(\d+)\}", raw)
    if mixed:
        whole, numerator, denominator = map(int, mixed.groups())
        if denominator == 0:
            return None
        part = Fraction(numerator, denominator)
        fraction = whole - part if whole < 0 else whole + part
        return float(fraction)
    try:
        import sympy as sp

        expression, _ = _latex_scalar_expression(raw)
        value_expr = sp.sympify(expression, locals={"sqrt": sp.sqrt, "root": sp.real_root, "pi": sp.pi})
        numeric = float(sp.N(value_expr, 30))
        return numeric if math.isfinite(numeric) else None
    except Exception:
        return None


def _round_nearest_integer(value: Fraction) -> int:
    """Round an exact fraction to the nearest integer, with halves away from zero."""
    magnitude = abs(value)
    rounded = (
        2 * magnitude.numerator + magnitude.denominator
    ) // (2 * magnitude.denominator)
    return rounded if value >= 0 else -rounded


def score(record: dict[str, Any], gold: str) -> None:
    answer = record.get("final_answer")
    if answer is None:
        record.update(correct=False, score_status="NO_ANSWER")
    else:
        predicted_number, gold_number = scalar_fraction(answer), scalar_fraction(gold)
        rounding_requested = bool(re.search(
            r"\bnearest\s+(?:whole\s+number|integer)\b",
            str(record.get("problem", "")),
            flags=re.IGNORECASE,
        ))
        if (
            rounding_requested
            and predicted_number is not None
            and gold_number is not None
            and gold_number.denominator == 1
        ):
            correct = _round_nearest_integer(predicted_number) == int(gold_number)
            record["score_method"] = "nearest_integer"
        elif predicted_number is not None and gold_number is not None:
            correct = predicted_number == gold_number
        else:
            predicted_approx, gold_approx = scalar_approx(answer), scalar_approx(gold)
            if predicted_approx is not None and gold_approx is not None:
                correct = math.isclose(predicted_approx, gold_approx, rel_tol=1e-6, abs_tol=1e-8)
                record["score_method"] = "numeric_tolerance"
            else:
                correct = answer_correct(answer, gold)
        record.update(correct=correct, score_status="MATCH" if correct else "MISMATCH")


def run_one(
    row: dict[str, Any], client: OllamaCloudClient, model: str, think: str,
    solver_call: Callable[..., Any] | None = None,
    *, temperature: float = 0.0,
) -> dict[str, Any]:
    solve = solver_call or (lambda function, *args: function(*args))
    started = time.monotonic()
    record: dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "id": row["unique_id"],
        "model": model,
        "temperature": temperature,
        "problem": row["problem"],
        "gold_answer": row["answer"],
    }
    try:
        raw = request_json(
            client, model, formalization_prompt(row["problem"]),
            FORMALIZATION_SCHEMA, think,
            system_prompt=FORMALIZATION_SYSTEM_PROMPT,
            temperature=temperature,
        )
        record["formalization"] = raw
        spec = ModelSpec.from_dict(raw)
        initial = solve(check_target_determinacy, spec)
        if initial.status in {CheckStatus.NOT_SUPPORTED, CheckStatus.INCONSISTENT}:
            corrected_raw = request_json(
                client, model,
                formalization_correction_prompt(
                    row["problem"], raw,
                    initial.reason or initial.status.value,
                ),
                FORMALIZATION_SCHEMA, think,
                system_prompt=FORMALIZATION_SYSTEM_PROMPT,
                temperature=temperature,
            )
            corrected_spec = ModelSpec.from_dict(corrected_raw)
            corrected_check = solve(check_target_determinacy, corrected_spec)
            record["formalization_attempt_1"] = raw
            record["formalization"] = corrected_raw
            record["formalization_retry"] = {
                "reason": initial.reason,
                "check": check_record(corrected_check),
            }
            raw, spec, initial = corrected_raw, corrected_spec, corrected_check
        record["initial_check"] = check_record(initial)
        if initial.status == CheckStatus.DETERMINATE:
            record.update(decision="ACCEPT", final_answer=initial.target_value)
        elif initial.status == CheckStatus.AMBIGUOUS:
            proposal = request_json(
                client, model, repair_prompt(row["problem"], raw, initial),
                REPAIR_SCHEMA, think, system_prompt=REPAIR_SYSTEM_PROMPT,
                temperature=temperature,
            )
            repaired, changed, reason = solve(apply_repair, row["problem"], spec, proposal)
            record["repair"] = {
                "proposal": proposal, "accepted": changed, "reason": reason,
            }
            if changed:
                final = solve(check_target_determinacy, repaired)
                record["final_check"] = check_record(final)
                if final.status == CheckStatus.DETERMINATE:
                    record.update(decision="REPAIRED", final_answer=final.target_value)
                else:
                    record.update(decision="ABSTAIN", reason="target_still_ambiguous")
            else:
                record.update(decision="ABSTAIN", reason=reason)
        else:
            record.update(decision="NO_CERTIFICATE", reason=initial.status.value)
        score(record, row["answer"])
        record["run_status"] = "ok"
    except Exception as exc:
        record.update(
            run_status="error", decision="PIPELINE_ERROR",
            error=f"{type(exc).__name__}: {str(exc)[:800]}",
        )
    record["wall_seconds"] = round(time.monotonic() - started, 2)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "Son/math500_scalar_degro.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "Son/results/degro_direct_strict_v4.jsonl")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--model", required=True)
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--only-id", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.temperature < 0:
        parser.error("--temperature must be nonnegative")

    rows = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines()]
    if args.only_id:
        selected = set(args.only_id)
        rows = [row for row in rows if row["unique_id"] in selected]
    if args.limit:
        rows = rows[: args.limit]
    completed: set[tuple[str, str]] = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            previous = json.loads(line)
            if previous.get("run_status") == "ok" and previous.get("pipeline_version") == PIPELINE_VERSION:
                completed.add((str(previous["id"]), str(previous["model"])))
    pending = [row for row in rows if (row["unique_id"], args.model) not in completed]
    print(json.dumps({
        "input_rows": len(rows), "pending": len(pending), "model": args.model,
        "temperature": args.temperature, "output": str(args.out),
        "workers": args.workers,
        "generated_python": False,
    }, ensure_ascii=False, indent=2), flush=True)
    if args.dry_run or not pending:
        return

    settings, keys = read_env(args.env)
    if not keys:
        raise SystemExit(f"No Ollama API keys found in {args.env}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    thread_state = threading.local()
    client_index = itertools.count()
    client_lock = threading.Lock()
    start_index = itertools.count(1)
    progress_lock = threading.Lock()

    def client_for_thread() -> OllamaCloudClient:
        client = getattr(thread_state, "client", None)
        if client is None:
            with client_lock:
                offset = next(client_index) % len(keys)
            rotated_keys = keys[offset:] + keys[:offset]
            client = OllamaCloudClient(
                rotated_keys, host=settings.get("OLLAMA_HOST", "https://ollama.com"),
                timeout_s=args.timeout,
            )
            thread_state.client = client
        return client

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="z3") as solver_pool:
        def solve(function: Callable[..., Any], *values: Any) -> Any:
            return solver_pool.submit(function, *values).result()

        def worker(row: dict[str, Any]) -> dict[str, Any]:
            with progress_lock:
                number = next(start_index)
                print(
                    f"[{number}/{len(pending)}] starting {row['unique_id']}",
                    flush=True,
                )
            return run_one(
                row, client_for_thread(), args.model, args.think, solve,
                temperature=args.temperature,
            )

        with ThreadPoolExecutor(
            max_workers=min(args.workers, len(pending)), thread_name_prefix="degro"
        ) as pool, args.out.open("a", encoding="utf-8") as stream:
            futures = {pool.submit(worker, row): row for row in pending}
            for index, future in enumerate(as_completed(futures), 1):
                row = futures[future]
                try:
                    record = future.result()
                except Exception as exc:
                    record = {
                        "pipeline_version": PIPELINE_VERSION, "id": row["unique_id"],
                        "model": args.model, "run_status": "error",
                        "decision": "WORKER_ERROR",
                        "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                    }
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                stream.flush()
                print(
                    f"[{index}/{len(pending)}] finished {record['id']} {record['decision']}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
