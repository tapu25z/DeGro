#!/usr/bin/env python3
"""AR-LSAT: problem -> ARModelSpec -> Z3 -> one grounded DeGro repair."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_math500_natural import REPAIR_SCHEMA, apply_repair, parse_object  # noqa: E402
from Son.run_degro_direct import read_env  # noqa: E402
from targetcheck.ar_lsat import ARCheckResult, check_ar_options, model_spec_from_ar  # noqa: E402
from targetcheck.providers import OllamaCloudClient  # noqa: E402

PIPELINE_VERSION = "ar_lsat_degro_v3_direct_spec"
LABELS = "ABCDE"

VARIABLE_SCHEMA = {
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
}
CONSTRAINT_SCHEMA = {
    "type": "object",
    "properties": {"id": {"type": "string"}, "expression": {"type": "string"}},
    "required": ["id", "expression"],
    "additionalProperties": False,
}
SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "variables": {"type": "array", "items": VARIABLE_SCHEMA},
        "constraints": {"type": "array", "items": CONSTRAINT_SCHEMA},
        "question_type": {
            "type": "string",
            "enum": ["COULD_TRUE", "MUST_TRUE", "CANNOT_TRUE", "COULD_FALSE", "MAXIMUM", "MINIMUM"],
        },
        "options": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": list(LABELS)},
                    "expression": {"type": "string"},
                    "rank": {"type": ["integer", "null"]},
                },
                "required": ["label", "expression", "rank"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["variables", "constraints", "question_type", "options"],
    "additionalProperties": False,
}

FORMALIZE_SYSTEM = """Return only one JSON ARModelSpec. Do not return Python, Markdown, prose, an answer label, or a solved conclusion. Extract every constraint only from the supplied passage and question."""
REPAIR_SYSTEM = """Add at most one missing constraint explicitly supported by the passage or question. Copy source_span verbatim. Never encode an answer option or answer label."""


def generate_json(
    client: OllamaCloudClient, model: str, prompt: str,
    schema: dict[str, Any], think: str, system: str,
) -> dict[str, Any]:
    response = client.chat(
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        format_schema=schema,
        options={"temperature": 0.0},
        think=think,
    )
    return parse_object(str(response.get("message", {}).get("content", "")))


def problem_prompt(row: dict[str, Any]) -> str:
    options = "\n".join(f"{label}. {text}" for label, text in row["options"].items())
    return f"""Translate this complete AR-LSAT item into one ARModelSpec.

PASSAGE:
{row['passage']}

QUESTION:
{row['question']}

OPTIONS:
{options}

Return exactly this JSON structure:
{{
  "variables": [{{"name": "x", "sort": "Int", "lower": 0,
                  "upper": 4, "values": null}}],
  "constraints": [{{"id": "c1", "expression": "x >= 0"}}],
  "question_type": "COULD_TRUE",
  "options": [{{"label": "A", "expression": "x == 1", "rank": null}},
              {{"label": "B", "expression": "x == 2", "rank": null}},
              {{"label": "C", "expression": "x == 3", "rank": null}},
              {{"label": "D", "expression": "x == 4", "rank": null}},
              {{"label": "E", "expression": "x == 0", "rank": null}}]
}}

Use descriptive Int/Real/Bool variables. Encode every passage rule and every
temporary condition in the question. Translate each option into one Boolean
expression over the declared variables.

Supported expressions: ==, !=, <, <=, >, >=, +, -, *, /, %, integer **,
and, or, Not, And, Or, Xor, Implies, If, Abs, Distinct, Sum, Count,
ExactlyOne, Exactly(k,...), AtMost(k,...), AtLeast(k,...).

Question types: COULD_TRUE, MUST_TRUE, CANNOT_TRUE, COULD_FALSE, MAXIMUM,
MINIMUM. For MAXIMUM/MINIMUM, rank is the option's comparable integer;
otherwise rank is null.

Use integer codes for finite categories. Do not use strings, lists inside
expressions, subscripts, comprehensions, quantifiers, &&, ||, or undeclared
functions. Every variable and constraint must be an object exactly as above.
Return variables, constraints, question_type, and exactly five options A-E.
Do not solve the item."""


def check_record(result: ARCheckResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "answer": result.answer,
        "candidates": list(result.candidates),
        "base_status": result.base_status,
        "options": [
            {
                "label": option.label,
                "positive": option.positive,
                "negative": option.negative,
                "rank": option.rank,
            }
            for option in result.options
        ],
        "reason": result.reason,
    }


def repair_prompt(row: dict[str, Any], raw: dict[str, Any], result: ARCheckResult) -> str:
    return f"""Z3 did not identify exactly one answer option.

PASSAGE:
{row['passage']}

QUESTION:
{row['question']}

CURRENT ARModelSpec:
{json.dumps(raw, ensure_ascii=False)}

Z3 RESULT:
{json.dumps(check_record(result), ensure_ascii=False)}

Return decision, source_span, constraint, and provenance. ADD_CONSTRAINT must
copy an exact source_span from the passage or question and use EXPLICIT_TEXT.
DOMAIN_SEMANTICS requires source_span=null. Otherwise return ABSTAIN."""


def run_one(
    row: dict[str, Any], client: OllamaCloudClient, model: str, think: str,
    solver_timeout_ms: int,
) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "id": row["unique_id"],
        "game_id": row["game_id"],
        "model": model,
        "problem": {key: row[key] for key in ("passage", "question", "options")},
        "gold_answer": row["answer"],
    }
    try:
        raw = generate_json(
            client, model, problem_prompt(row), SPEC_SCHEMA, think,
            FORMALIZE_SYSTEM,
        )
        record["formalization"] = raw
        initial = check_ar_options(raw, timeout_ms=solver_timeout_ms)
        record["initial_check"] = check_record(initial)

        if initial.status == "UNIQUE":
            record.update(decision="ACCEPT", final_answer=initial.answer)
        elif initial.status in {"NO_OPTION", "MULTIPLE_OPTIONS"}:
            proposal = generate_json(
                client, model, repair_prompt(row, raw, initial), REPAIR_SCHEMA,
                think, REPAIR_SYSTEM,
            )
            source = row["passage"] + "\n" + row["question"]
            repaired, changed, reason = apply_repair(
                source, model_spec_from_ar(raw), proposal
            )
            record["repair"] = {"proposal": proposal, "accepted": changed, "reason": reason}
            if changed:
                repaired_raw = dict(raw)
                repaired_raw["constraints"] = [
                    {"id": constraint.id, "expression": constraint.expression}
                    for constraint in repaired.constraints
                ]
                final = check_ar_options(repaired_raw, timeout_ms=solver_timeout_ms)
                record["final_check"] = check_record(final)
                if final.status == "UNIQUE":
                    record.update(decision="REPAIRED", final_answer=final.answer)
                else:
                    record.update(decision="ABSTAIN", reason="target_still_not_unique")
            else:
                record.update(decision="ABSTAIN", reason=reason)
        else:
            record.update(decision="NO_CERTIFICATE", reason=initial.reason or initial.status)

        record["correct"] = record.get("final_answer") == row["answer"]
        record["score_status"] = (
            "MATCH" if record["correct"]
            else "NO_ANSWER" if record.get("final_answer") is None
            else "MISMATCH"
        )
        record["run_status"] = "ok"
    except Exception as exc:
        record.update(
            decision="PIPELINE_ERROR", run_status="error", correct=False,
            score_status="NO_ANSWER", error=f"{type(exc).__name__}: {str(exc)[:800]}",
        )
    record["wall_seconds"] = round(time.monotonic() - started, 2)
    return record


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/ar_lsat/test.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "Son/results/ar_lsat_degro_v3.jsonl")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--model", required=True)
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--solver-timeout-ms", type=int, default=5_000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")

    rows = load_jsonl(args.data)
    if args.limit:
        rows = rows[: args.limit]
    completed = {
        (record.get("id"), record.get("model"))
        for record in load_jsonl(args.out)
        if record.get("pipeline_version") == PIPELINE_VERSION and record.get("run_status") == "ok"
    }
    pending = [row for row in rows if (row["unique_id"], args.model) not in completed]
    print(json.dumps({
        "input_questions": len(rows), "pending": len(pending),
        "model": args.model, "workers": args.workers,
        "flow": "problem -> ARModelSpec -> Z3 -> DeGro -> Z3",
        "output": str(args.out),
    }, indent=2), flush=True)
    if args.dry_run or not pending:
        return

    settings, keys = read_env(args.env)
    if not keys:
        raise SystemExit(f"No Ollama API keys found in {args.env}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    thread_state = threading.local()
    client_index = itertools.count()
    client_lock = threading.Lock()

    def client_for_thread() -> OllamaCloudClient:
        client = getattr(thread_state, "client", None)
        if client is None:
            with client_lock:
                offset = next(client_index) % len(keys)
            rotated = keys[offset:] + keys[:offset]
            client = OllamaCloudClient(
                rotated, host=settings.get("OLLAMA_HOST", "https://ollama.com"),
                timeout_s=args.timeout,
            )
            thread_state.client = client
        return client

    def worker(row: dict[str, Any]) -> dict[str, Any]:
        return run_one(row, client_for_thread(), args.model, args.think, args.solver_timeout_ms)

    with ThreadPoolExecutor(max_workers=min(args.workers, len(pending))) as pool, args.out.open("a", encoding="utf-8") as stream:
        futures = {pool.submit(worker, row): row for row in pending}
        for index, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                record = {
                    "pipeline_version": PIPELINE_VERSION, "id": row["unique_id"],
                    "model": args.model, "decision": "WORKER_ERROR", "run_status": "error",
                    "correct": False, "score_status": "NO_ANSWER",
                    "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                }
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            stream.flush()
            print(
                f"[{index}/{len(pending)}] {record['id']} {record['decision']} "
                f"{'CORRECT' if record.get('correct') else 'WRONG'}",
                flush=True,
            )


if __name__ == "__main__":
    main()
