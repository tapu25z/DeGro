#!/usr/bin/env python3
"""Run a direct-answer LLM baseline on the same cohort as direct DeGro."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Son.run_degro_direct import read_env, request_json, score  # noqa: E402
from targetcheck.providers import OllamaCloudClient  # noqa: E402


PIPELINE_VERSION = "llm_direct_answer_v2_no_implicit_cardinality"
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"final_answer": {"type": "string"}},
    "required": ["final_answer"],
    "additionalProperties": False,
}


def direct_prompt(problem: str) -> str:
    return f"""Solve the following mathematics problem.

Problem:
{problem}

Return exactly one JSON object with a concise final_answer string. Do not return
a ModelSpec, Python code, explanation, derivation, or additional fields.
Example: {{"final_answer":"3/2"}}"""


def run_one(
    row: dict[str, Any], client: OllamaCloudClient, model: str, think: str,
    temperature: float = 0.0,
) -> dict[str, Any]:
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
        output = request_json(
            client, model, direct_prompt(row["problem"]), ANSWER_SCHEMA, think,
            temperature=temperature,
        )
        record["final_answer"] = output["final_answer"]
        score(record, row["answer"])
        record.update(run_status="ok", decision="DIRECT_ANSWER")
    except Exception as exc:
        record.update(
            run_status="error",
            decision="PIPELINE_ERROR",
            correct=False,
            score_status="NO_ANSWER",
            error=f"{type(exc).__name__}: {str(exc)[:800]}",
        )
    record["wall_seconds"] = round(time.monotonic() - started, 2)
    return record


def load_records(path: Path, *, version: str | None = None, model: str | None = None) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if version is not None and record.get("pipeline_version") != version:
            continue
        if model is not None and record.get("model") != model:
            continue
        if isinstance(record.get("id"), str):
            records[record["id"]] = record
    return records


def print_summary(direct: dict[str, dict[str, Any]], degro_path: Path) -> None:
    completed = [record for record in direct.values() if record.get("run_status") == "ok"]
    direct_correct = sum(record.get("correct") is True for record in completed)
    print(
        json.dumps(
            {
                "direct_completed": len(completed),
                "direct_correct": direct_correct,
                "direct_accuracy": round(direct_correct / len(completed), 6) if completed else None,
                "direct_status": dict(Counter(record.get("score_status") for record in direct.values())),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )

    degro = load_records(degro_path)
    common_ids = sorted(set(direct) & set(degro))
    if not common_ids:
        return
    both_correct = direct_only = degro_only = both_wrong = 0
    for problem_id in common_ids:
        direct_ok = direct[problem_id].get("correct") is True
        degro_ok = degro[problem_id].get("correct") is True
        if direct_ok and degro_ok:
            both_correct += 1
        elif direct_ok:
            direct_only += 1
        elif degro_ok:
            degro_only += 1
        else:
            both_wrong += 1
    direct_total = both_correct + direct_only
    degro_total = both_correct + degro_only
    total = len(common_ids)
    print(
        json.dumps(
            {
                "paired_n": total,
                "direct_correct": direct_total,
                "direct_accuracy": round(direct_total / total, 6),
                "degro_correct": degro_total,
                "degro_accuracy": round(degro_total / total, 6),
                "degro_minus_direct_percentage_points": round(
                    100 * (degro_total - direct_total) / total, 3
                ),
                "both_correct": both_correct,
                "direct_only_correct": direct_only,
                "degro_only_correct": degro_only,
                "both_wrong": both_wrong,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "Son/math500_scalar_degro.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "Son/results/llm_direct_v2.jsonl")
    parser.add_argument(
        "--degro-log", type=Path,
        default=ROOT / "Son/results/degro_direct_strict_v4.jsonl",
    )
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

    existing = load_records(args.out, version=PIPELINE_VERSION, model=args.model)
    completed_ids = {
        problem_id for problem_id, record in existing.items()
        if record.get("run_status") == "ok"
    }
    pending = [row for row in rows if row["unique_id"] not in completed_ids]
    print(
        json.dumps(
            {
                "input_rows": len(rows),
                "pending": len(pending),
                "model": args.model,
                "think": args.think,
                "temperature": args.temperature,
                "output": str(args.out),
                "workers": args.workers,
                "mode": "direct_answer_without_modelspec_or_z3",
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    if args.dry_run:
        return
    if not pending:
        print_summary(existing, args.degro_log)
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
                rotated_keys,
                host=settings.get("OLLAMA_HOST", "https://ollama.com"),
                timeout_s=args.timeout,
            )
            thread_state.client = client
        return client

    def worker(row: dict[str, Any]) -> dict[str, Any]:
        with progress_lock:
            number = next(start_index)
            print(f"[{number}/{len(pending)}] starting {row['unique_id']}", flush=True)
        return run_one(
            row, client_for_thread(), args.model, args.think, args.temperature
        )

    with ThreadPoolExecutor(max_workers=min(args.workers, len(pending))) as pool, args.out.open(
        "a", encoding="utf-8"
    ) as stream:
        futures = {pool.submit(worker, row): row for row in pending}
        for index, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                record = {
                    "pipeline_version": PIPELINE_VERSION,
                    "id": row["unique_id"],
                    "model": args.model,
                    "run_status": "error",
                    "decision": "WORKER_ERROR",
                    "correct": False,
                    "score_status": "NO_ANSWER",
                    "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                }
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            stream.flush()
            print(
                f"[{index}/{len(pending)}] finished {record['id']} "
                f"{'CORRECT' if record.get('correct') else 'WRONG'}",
                flush=True,
            )

    final_records = load_records(args.out, version=PIPELINE_VERSION, model=args.model)
    print_summary(final_records, args.degro_log)


if __name__ == "__main__":
    main()
