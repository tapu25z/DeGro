#!/usr/bin/env python3
"""Direct answers vs LLM ModelSpec -> Z3; standalone except for z3-solver.
Run from the repo root: .venv/bin/python scripts/alg514_two_flows.py --limit 3
Named targets follow question order; unnamed pairs may agree up to permutation.
Scoring: ordered gold_answers when supplied; otherwise ALG514-compatible subset
matching against gold_solutions (does not verify requested order), tolerance 1e-3.
Ambiguous specifications enter bounded source-grounded additive repair.
The default dataset includes one/two-target questions, excluding reviewed limits.
"""

import argparse
import ast
import hashlib
import http.client
import json
import keyword
import math
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from fractions import Fraction
from pathlib import Path
from threading import Condition

import z3


class APIError(Exception):
    """No usable API response after trying other keys; exclude from accuracy."""


class KeyPool:
    """Lease distinct idle keys; share cooldowns across all workers."""
    def __init__(self, count):
        self.condition = Condition()
        self.available = [0.0] * count
        self.busy = set()
        self.cursor = 0

    def get(self, tried):
        with self.condition:
            while True:
                now = time.monotonic()
                candidates = [(self.cursor + i) % len(self.available)
                              for i in range(len(self.available))]
                idle = [i for i in candidates if i not in tried and i not in self.busy]
                for i in idle:
                    if self.available[i] <= now:
                        self.busy.add(i)
                        self.cursor = (i + 1) % len(self.available)
                        return i
                wait = min((self.available[i] - now for i in idle), default=1.0)
                self.condition.wait(timeout=max(0.01, min(wait, 1.0)))

    def put(self, index, cooldown=0):
        with self.condition:
            self.busy.remove(index)
            self.available[index] = time.monotonic() + cooldown
            self.condition.notify_all()


DIRECT = """You solve algebra word problems accurately.
Identify exactly which quantities are requested and their units. Check each
relation, arithmetic, and unit conversion before returning your answer.
Return only JSON with one field: {"answers":["value1","value2"]}.
Use one string per requested quantity, in question order. For example, two
answers 7 and 3/2 must be ["7","3/2"], never ["7/1.5"]. A slash within one
string denotes a single fraction, not a separator between answers.
Do not include unrequested quantities, prose, or Markdown. Do not guess unstated
facts. Follow the source wording rather than presumed benchmark conventions."""
SYNTAX = """Use Python expressions: declared variables, numerical literals,
parentheses, + - * /, integer %, **0..4, == != < <= > >=, and/or/not.
Parenthesize combined comparisons. Sorts belong ONLY in variables JSON:
write 0.75, never (0.75 : Real). No thousands separators inside literals.
No =, &&, ||, &, |, ^, function calls, Z3 constructors, statements or Markdown."""

SPEC = """Translate the source faithfully for Z3. Return ONLY JSON:
{"status":"SUPPORTED","variables":{"a":"Real","b":"Real"},
"constraints":["a+b == 10","a-b == 2"],"targets":["a","b"],
"unordered_targets":true}.
1. Declare EVERY referenced name using Python identifiers. Prefer existing
variables as targets. Declaring a target alias is not enough: bind it to the
encoded quantities. Use constants for known inputs, or declare AND bind them.
2. Identify the requested mathematical quantity or quantities from the source.
Represent each as a target expression over the declared variables, preserving
the requested meaning, order and units. Do not substitute a different quantity.
3. For two interchangeable numbers/objects without distinct source roles,
set unordered_targets=true, even if you name them a/b or s1/s2. Preserve both
relation orientations as a disjunction. Named roles or explicitly requested
order use false. ONE target ALWAYS uses false, regardless of other variables.
4. If target aliases are needed, define them explicitly in terms of the encoded
variables. Apply ordering only when justified by the requested source roles.
5. Encode all explicit numerical facts and relations, preserving their scope,
direction, coefficients and units. Distinguish known parameters from unknown
quantities; do not omit known values or multipliers.
6. Use Int for indivisible counts/explicit integers; Real for time, money,
rates, measurements and arbitrary numbers. Do not change domains, invent facts,
choose a disjunction branch or pin a computed answer just to force determinacy.
7. Before returning, read the specification back as a mathematical description
and compare it with the source. Check that every referenced name is declared,
target aliases have definitions, known parameters are bound, each source
relation is represented, and targets express exactly what the question asks.
Check units and whether target permutations preserve the requested meaning.
If a check fails, correct the representation from the source before output:
fix inconsistent references, supply omitted definitions, restore omitted
source relations, or correct the target expression/ordering metadata.
Do not make an underdetermined source determinate by inventing information.
For optimization, interval-valued or threshold answers, or unsupported
operations, return
{"status":"NOT_SUPPORTED","variables":{},"constraints":[],"targets":[]}.
""" + SYNTAX

SCHEMA_FIX = """Your previous ModelSpec failed schema/compilation checks.
Return a corrected complete ModelSpec, obeying the schema below. Make only the
necessary syntax, declaration, naming, or target-binding corrections. Preserve
source facts, numerical values, variable domains and quantity meanings; do not
invent a relation or computed answer. Declare and bind missing names or use the
existing declared names consistently. This is format correction, not additive
ambiguity repair. You receive no gold answer.
""" + SPEC

REPAIR = """Z3 reports AMBIGUOUS. Recover missing source-supported facts
without changing existing variables, sorts, constraints, roles, or targets.
Return ONLY JSON:
{"decision":"add-constraint","source_span":"verbatim source text",
"constraint":"a+b == 10"}.
Compare the current specification with the source to identify an omitted
source-supported binding, definition, or relation that affects the target.
Also check target aliases: if declared but unbound, link them to existing
quantities according to the requested source roles/order. A restriction on
other variables cannot fix a disconnected target. An alias needs a definition
in terms of the original encoded variables.
Bind stated parameter values directly; do not pin the target to a computed
answer. If several omitted facts are needed, combine them with and in ONE Boolean
expression and quote an exact contiguous source span supporting ALL of them.
Copy the span verbatim, including capitalization and punctuation; do not
paraphrase, lowercase, or join separate spans.
Keep source roles, relation direction, multipliers, and units. Never guess,
repeat entailed facts, or turn a limit into an equality. Do not add arbitrary
ordering or change variable meanings or unordered_targets during repair.
Never select one orientation of a disjunction solely to force determinacy.
For unordered pairs, AMBIGUOUS means a different pair of values, not a swap.
Acceptance requires compilation, a source citation, non-redundancy,
consistency, and restored target determinacy.
If no justified sufficient addition exists, return
{"decision":"abstain","source_span":"","constraint":""}.
""" + SYNTAX


def expression(source, variables):
    """Compile a small arithmetic AST without eval or executing generated code."""

    def visit(node):
        if isinstance(node, ast.Name):
            return variables[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return (z3.IntVal if type(node.value) is int else z3.RealVal)(
                str(node.value), ctx=context
            )
        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.Not):
                return z3.Not(value)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                denominators.append(right != 0)
                return real(left) / real(right)
            if isinstance(node.op, ast.Mod):
                denominators.append(right != 0)
                return left % right
            if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
                if type(node.right.value) is int and 0 <= node.right.value <= 4:
                    return left**node.right.value
        if isinstance(node, ast.Compare):
            values = [visit(n) for n in [node.left, *node.comparators]]
            operators = {
                ast.Eq: lambda a, b: a == b,
                ast.NotEq: lambda a, b: a != b,
                ast.Lt: lambda a, b: a < b,
                ast.LtE: lambda a, b: a <= b,
                ast.Gt: lambda a, b: a > b,
                ast.GtE: lambda a, b: a >= b,
            }
            return z3.And(
                *[
                    operators[type(op)](a, b)
                    for op, a, b in zip(node.ops, values, values[1:])
                ]
            )
        if isinstance(node, ast.BoolOp):
            return (z3.And if isinstance(node.op, ast.And) else z3.Or)(
                *[visit(n) for n in node.values]
            )
        raise ValueError(f"Unsupported expression: {source}")

    context = next(iter(variables.values())).ctx
    denominators = []
    real = lambda value: z3.ToReal(value) if z3.is_int(value) else value
    return visit(ast.parse(source, mode="eval").body), denominators


def validate_spec(spec):
    """Reject invalid identifiers and undeclared references before Z3."""
    if not isinstance(spec, dict) or spec.get("status") not in ("SUPPORTED", "NOT_SUPPORTED"):
        raise ValueError("Expected ModelSpec object with a valid status")
    if spec["status"] == "NOT_SUPPORTED":
        return
    if not isinstance(spec.get("variables"), dict) or not spec["variables"]:
        raise ValueError("Invalid ModelSpec")
    for name, sort in spec["variables"].items():
        if not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError(f"Invalid variable name: {name!r}; use Python identifiers")
        if sort not in ("Int", "Real"):
            raise ValueError(f"Invalid sort: {sort}")
    if not isinstance(spec.get("constraints"), list):
        raise ValueError("constraints must be a list of expression strings")
    if not isinstance(spec.get("targets"), list) or not 1 <= len(spec["targets"]) <= 2:
        raise ValueError("Expected 1-2 targets")
    if type(spec.get("unordered_targets", False)) is not bool:
        raise ValueError("unordered_targets must be Boolean")
    if spec.get("unordered_targets", False) and len(spec["targets"]) != 2:
        raise ValueError("Only a two-target answer may be unordered")
    for source in [*spec["constraints"], *spec["targets"]]:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Constraints and targets must be nonempty strings")
        names = {n.id for n in ast.walk(ast.parse(source, mode="eval"))
                 if isinstance(n, ast.Name)}
        missing = names - spec["variables"].keys()
        if missing:
            raise ValueError(f"Undeclared names: {', '.join(sorted(missing))}")


def compile_spec(spec, timeout):
    validate_spec(spec)
    if spec["status"] != "SUPPORTED":
        raise ValueError("Cannot compile unsupported ModelSpec")
    context = z3.Context()
    variables = {name: (z3.Int if sort == "Int" else z3.Real)(name, ctx=context)
                 for name, sort in spec["variables"].items()}
    solver = z3.Solver(ctx=context)
    solver.set(timeout=timeout)
    for source in spec["constraints"]:
        term, bounds = expression(source, variables)
        solver.add(term, *bounds)
    targets = []
    for source in spec["targets"]:
        term, bounds = expression(source, variables)
        if not z3.is_arith(term):
            raise ValueError("Target must be numerical")
        targets.append(term)
        solver.add(*bounds)
    return solver, variables, targets


def solve(spec, timeout):
    """Check target agreement, allowing swaps only for an explicitly unordered pair."""
    validate_spec(spec)
    if spec.get("status") == "NOT_SUPPORTED":
        return "NOT_SUPPORTED", []
    solver, _, targets = compile_spec(spec, timeout)
    status = solver.check()
    if status != z3.sat:
        return ("INCONSISTENT" if status == z3.unsat else "UNKNOWN"), []
    model = solver.model()
    values = [model.eval(t, model_completion=True) for t in targets]
    same = z3.And(*[target == value for target, value in zip(targets, values)])
    if spec.get("unordered_targets", False):
        swapped = z3.And(targets[0] == values[1], targets[1] == values[0])
        same = z3.Or(same, swapped)
    # Look for a genuinely different answer, beyond any permitted permutation.
    solver.add(z3.Not(same))
    status = solver.check()
    if status != z3.unsat:
        return ("AMBIGUOUS" if status == z3.sat else "UNKNOWN"), []
    answers = [
        str(v)
        if z3.is_int_value(v) or z3.is_rational_value(v)
        else v.as_decimal(16).rstrip("?")
        for v in values
    ]
    return "DETERMINATE", answers


def checked_modelspec(problem, raw, request, timeout, attempts, trace):
    """One bounded schema correction if generation cannot be parsed/compiled."""
    for attempt in range(attempts + 1):
        try:
            spec = json.loads(raw)
            status, answers = solve(spec, timeout)
            if attempt:
                trace.append(dict(attempt=attempt, result="VALIDATED", raw=raw))
            return spec, status, answers
        except (ValueError, KeyError, TypeError, SyntaxError, z3.Z3Exception) as exc:
            error = f"{type(exc).__name__}: {exc}"
            trace.append(dict(attempt=attempt, result="INVALID_SCHEMA", raw=raw, error=error))
            if attempt == attempts:
                raise
            raw = request(SCHEMA_FIX, json.dumps({"problem": problem,
                "previous_output": raw, "compiler_error": error}, ensure_ascii=False))


def grounded_repair(problem, spec, request, timeout, attempts):
    """Add a cited constraint only after novelty, consistency, determinacy checks."""
    trace = []
    for attempt in range(attempts):
        entry = {"attempt": attempt + 1}
        try:
            raw = request(REPAIR, json.dumps({"problem": problem,
                "modelspec": spec, "verdict": "AMBIGUOUS",
                "previous_attempts": trace}, ensure_ascii=False))
            entry["raw"] = raw
            entry["proposal"] = proposal = json.loads(raw)
            if proposal.get("decision") == "abstain":
                entry["result"] = "ABSTAIN"
                trace.append(entry)
                break
            if proposal.get("decision") != "add-constraint":
                raise ValueError("Expected add-constraint or abstain")
            span, constraint = proposal["source_span"], proposal["constraint"]
            if not isinstance(span, str) or not span.strip() or span not in problem:
                raise ValueError("Supporting span must occur verbatim in the source")
            if not isinstance(constraint, str) or not constraint.strip():
                raise ValueError("Expected a nonempty constraint string")
            solver, variables, _ = compile_spec(spec, timeout)
            term, bounds = expression(constraint, variables)
            solver.add(*bounds, z3.Not(term))
            if solver.check() != z3.sat:
                raise ValueError("Addition is redundant or novelty is inconclusive")
            candidate = dict(spec, constraints=[*spec["constraints"], constraint])
            status, answers = solve(candidate, timeout)
            if status != "DETERMINATE":
                raise ValueError(f"Repair must restore determinacy; got {status}")
            entry["result"] = "ACCEPTED"
            trace.append(entry)
            return status, answers, candidate, trace
        except APIError as exc:
            entry.update(result="API_ERROR", reason=str(exc))
            exc.repair_trace = [*trace, entry]
            raise
        except Exception as exc:
            entry.update(result="REJECTED", reason=f"{type(exc).__name__}: {exc}")
            trace.append(entry)
    return "NO_ADMISSIBLE_REPAIR_FOUND", [], spec, trace


def correct(answers, gold, ordered=False):
    if not isinstance(answers, list) or not 0 < len(answers) <= len(gold):
        return False
    remaining = list(gold)
    try:
        if ordered:
            return len(answers) == len(gold) and all(
                math.isclose(float(Fraction(str(a))), float(Fraction(str(g))),
                             rel_tol=1e-3, abs_tol=1e-3)
                for a, g in zip(answers, gold)
            )
        for answer in answers:
            value = float(Fraction(str(answer)))
            index = next(
                (
                    i
                    for i, g in enumerate(remaining)
                    if math.isclose(value, g, rel_tol=1e-3, abs_tol=1e-3)
                ),
                None,
            )
            if index is None:
                return False
            remaining.pop(index)
    except (ValueError, ZeroDivisionError, OverflowError):
        return False
    return True


def chat(payload, keys, key_pool):
    """Retry API/transport failures on other keys, without repeated 429 storms."""
    tried, failures = set(), []
    while len(tried) < len(keys):
        index = key_pool.get(tried)
        tried.add(index)
        cooldown = 0
        try:
            request = urllib.request.Request(
                "https://ollama.com/api/chat", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + keys[index]},
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.load(response)
            content = body["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Invalid API response content")
            return content
        except urllib.error.HTTPError as exc:
            failures.append(f"HTTP {exc.code}")
            cooldown = 60 if exc.code == 429 else 2
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after:
                try:
                    cooldown = max(cooldown, float(retry_after))
                except ValueError:
                    try:
                        cooldown = max(cooldown,
                            parsedate_to_datetime(retry_after).timestamp() - time.time())
                    except (ValueError, TypeError, OverflowError):
                        pass
        except (OSError, urllib.error.URLError, http.client.HTTPException,
                ValueError, KeyError, TypeError) as exc:
            failures.append(type(exc).__name__)
            cooldown = 2
        finally:
            key_pool.put(index, cooldown)
    raise APIError(f"API failed on {len(tried)} distinct keys: {', '.join(failures)}")


def scores(records):
    """API failures are unscored; model output and solver failures stay in denominator."""
    scored = [r for r in records if r["status"] != "API_ERROR"]
    n = sum(bool(r["correct"]) for r in scored)
    accuracy = f"{n / len(scored):.2%}" if scored else "N/A"
    return (f"{n}/{len(scored)} = {accuracy}; "
            f"api_excluded={len(records) - len(scored)}; "
            f"errors={sum(r['status'] == 'ERROR' for r in scored)}; "
            f"coverage={len(scored)}/{len(records)}")


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path,
                        default=root / "data/alg514/alg514_supported.jsonl")
    parser.add_argument("--keys", type=Path, default=root / "api.txt",
                        help="Key file; defaults to api.txt, OLLAMA_API_KEY, or .env")
    parser.add_argument(
        "--out", type=Path, default=root / "results/alg514_degro_pairs.jsonl"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-oss:20b", "gpt-oss:120b", "nemotron-3-nano:30b"],
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8, help="Concurrent requests")
    parser.add_argument("--last-keys", type=int, default=0,
                        help="Use only the last N keys in the key file; 0 uses all")
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--think", choices=["true", "false", "low", "medium", "high"],
                        default="low")
    parser.add_argument("--solver-ms", type=int, default=5000)
    parser.add_argument("--repair-attempts", type=int, default=2,
                        help="Grounded repair proposals after AMBIGUOUS; 0 disables")
    parser.add_argument("--schema-attempts", type=int, default=1,
                        help="Corrections after invalid JSON/schema/compilation; 0 disables")
    args = parser.parse_args()
    if (args.limit < 0 or args.solver_ms <= 0 or args.workers < 1
            or args.last_keys < 0 or args.repair_attempts < 0 or args.schema_attempts < 0):
        parser.error("Invalid limit, timeout, workers, or last-keys")
    keys = []
    if args.keys.is_file():
        key_lines = args.keys.read_text().splitlines()
    elif os.environ.get("OLLAMA_API_KEY"):
        key_lines = [os.environ["OLLAMA_API_KEY"]]
    elif (root / ".env").is_file():
        key_lines = (root / ".env").read_text().splitlines()
    else:
        key_lines = []
    for line in key_lines:
        line = line.split("#", 1)[0].strip().removeprefix("export ")
        if "=" in line:
            name, line = line.split("=", 1)
            if not name.strip().startswith(("OLLAMA", "API_KEY")):
                continue
        if line.strip():
            keys.append(line.split()[-1].strip("\"'"))
    if not keys:
        parser.error("No API key: add keys to .env, use --keys /path/to/keyfile, "
                     "or set OLLAMA_API_KEY")
    if args.last_keys > len(keys):
        parser.error(f"Only {len(keys)} keys available; cannot select {args.last_keys}")
    if args.last_keys:
        keys = keys[-args.last_keys:]
    keys = list(dict.fromkeys(keys))
    key_pool = KeyPool(len(keys))
    workers = min(args.workers, len(keys))
    print(f"Using {workers} workers and {len(keys)} keys", flush=True)
    rows = [
        json.loads(line) for line in args.data.read_text().splitlines() if line.strip()
    ]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        parser.error("Empty dataset")
    # Resume only identical code, dataset, and settings; errors are retried.
    protocol = hashlib.sha256(
        Path(__file__).read_bytes()
        + args.data.read_bytes()
        + str((args.temperature, args.think, args.solver_ms,
               args.repair_attempts, args.schema_attempts)).encode()
    ).hexdigest()
    saved = {}
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            r = json.loads(line)
            if r.get("protocol") == protocol:
                saved[r["model"], r["flow"], r["id"]] = r
    def run(model, row, flow, prompt):
        think = {"true": True, "false": False}.get(args.think, args.think)
        ordered = "gold_answers" in row
        r = dict(model=model, flow=flow, id=row["unique_id"], protocol=protocol,
                 temperature=args.temperature, think=think,
                 gold=row["gold_answers"] if ordered else row["gold_solutions"],
                 scoring="ordered_answers" if ordered else "alg514_compatible",
                 answers=[], correct=False, scored=True)
        def request(system, user):
            payload = dict(model=model, stream=False, format="json", think=think,
                options={"temperature": args.temperature},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}])
            return chat(payload, keys, key_pool)
        try:
            r["raw"] = request(prompt, row["problem"])
            if flow == "direct":
                r["output"] = output = json.loads(r["raw"])
                r.update(status="OK", answers=output["answers"])
            else:
                r["schema_trace"] = []
                output, status, answers = checked_modelspec(
                    row["problem"], r["raw"], request, args.solver_ms,
                    args.schema_attempts, r["schema_trace"])
                r.update(output=output, schema_corrected=bool(r["schema_trace"]))
                r["initial_status"] = status
                if status == "AMBIGUOUS" and args.repair_attempts:
                    status, answers, final_spec, trace = grounded_repair(
                        row["problem"], output, request, args.solver_ms,
                        args.repair_attempts)
                    r.update(repaired_spec=final_spec, repair_trace=trace)
                r.update(status=status, answers=answers, targets=output.get("targets", []),
                         unordered_targets=output.get("unordered_targets", False))
            r["correct"] = correct(r["answers"], r["gold"], ordered)
        except APIError as exc:
            r.update(status="API_ERROR", correct=None, scored=False,
                     error=f"{type(exc).__name__}: {exc}")
            if hasattr(exc, "repair_trace"):
                r["repair_trace"] = exc.repair_trace
        except Exception as exc:
            r.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
        return r

    jobs = [(model, row, flow, prompt) for model in args.models for row in rows
            for flow, prompt in (("direct", DIRECT), ("modelspec_z3", SPEC))
            if saved.get((model, flow, row["unique_id"]), {}).get("status", "ERROR")
                in ("ERROR", "API_ERROR")]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as stream, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, *job) for job in jobs]
        for future in as_completed(futures):
            r = future.result()
            saved[r["model"], r["flow"], r["id"]] = r
            stream.write(json.dumps(r, ensure_ascii=False) + "\n")
            stream.flush()
            print(r["model"], r["flow"], r["id"], r["status"], r["answers"],
                  r["correct"] if r["scored"] else "UNSCORED",
                  r.get("error", ""), flush=True)
    for model in args.models:
        for flow in ("direct", "modelspec_z3"):
            records = [saved[model, flow, row["unique_id"]] for row in rows]
            for scoring in sorted({r["scoring"] for r in records}):
                subset = [r for r in records if r["scoring"] == scoring]
                print(f"{model} {flow} {scoring}: {scores(subset)}")
        # Compare both flows on the same questions when API coverage differs.
        paired_ids = [row["unique_id"] for row in rows if all(
            saved[model, flow, row["unique_id"]]["status"] != "API_ERROR"
            for flow in ("direct", "modelspec_z3"))]
        for flow in ("direct", "modelspec_z3"):
            matched = [saved[model, flow, uid] for uid in paired_ids]
            print(f"{model} {flow} matched_cases: {scores(matched)}")


if __name__ == "__main__":
    main()
