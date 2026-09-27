#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import local
from typing import Any

from targetcheck.providers import OllamaCloudClient, load_api_keys


LABELS = (
    "CORRECT_FORMALIZATION",
    "MISSING_CONSTRAINT",
    "WRONG_CONSTRAINT",
    "EXTRA_UNSUPPORTED_CONSTRAINT",
    "WRONG_TARGET",
    "COMPUTATION_OR_SELECTION_ERROR",
    "UNSUPPORTED_TO_AUDIT",
)

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": list(LABELS)},
        "missing_fact": {"type": ["string", "null"]},
        "source_evidence": {"type": ["string", "null"]},
        "code_evidence": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    },
    "required": [
        "label",
        "missing_fact",
        "source_evidence",
        "code_evidence",
        "reason",
        "confidence",
    ],
    "additionalProperties": False,
}


def audit_prompt(problem: str, gold_equations: list[str], code: str, answer: str) -> str:
    return f"""Audit whether this executed SymCode program faithfully encodes the mathematical problem.

Problem:
{problem}

Dataset reference equations (semantic reference only; algebraically equivalent forms are valid):
{json.dumps(gold_equations, ensure_ascii=False)}

Executed program:
```python
{code}
```

Executed answer:
{answer}

Classify the primary defect in the executable logic before the final answer is printed.

- CORRECT_FORMALIZATION: all target-relevant source facts are encoded correctly; algebraically equivalent transformations are allowed.
- MISSING_CONSTRAINT: a target-relevant relation explicitly supported by the problem is absent, so the encoded equations/conditions do not by themselves determine the requested target. Use this only for a genuine omitted relation, not for a wrong translation.
- WRONG_CONSTRAINT: a source relation is present but mistranslated, uses a wrong coefficient/operator/sign, or is replaced by a different relation.
- EXTRA_UNSUPPORTED_CONSTRAINT: the code adds a material assumption not licensed by the source.
- WRONG_TARGET: the code solves for or returns the wrong requested quantity or ordering.
- COMPUTATION_OR_SELECTION_ERROR: the source model is present, but solving, indexing, filtering, simplification, or printing produces the wrong result.
- UNSUPPORTED_TO_AUDIT: the program cannot be judged reliably in this taxonomy.

Do not call a relation missing when the code enforces it through substitution, an equivalent expression, a domain restriction, or direct computation. For MISSING_CONSTRAINT, quote the missing source fact and state the absent mathematical relation. Return only the JSON object."""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def completed(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    done = set()
    for row in load_jsonl(path):
        if row.get("status") == "ok":
            done.add((row["id"], row["generator_model"]))
    return done


def normalized_audit(raw: dict[str, Any]) -> dict[str, Any]:
    label = next(
        (
            raw.get(key)
            for key in (
                "label",
                "classification",
                "defect",
                "defect_type",
                "defect_category",
                "category",
                "result",
            )
            if raw.get(key) in LABELS
        ),
        "UNSUPPORTED_TO_AUDIT",
    )
    return {
        "label": label,
        "missing_fact": raw.get("missing_fact"),
        "source_evidence": raw.get("source_evidence"),
        "code_evidence": raw.get("code_evidence"),
        "reason": str(raw.get("reason") or raw.get("explanation") or ""),
        "confidence": raw.get("confidence") if raw.get("confidence") in {"HIGH", "MEDIUM", "LOW"} else "LOW",
    }


def choose_jobs(
    results: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    models: tuple[str, ...],
    sample_size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    artifacts: dict[tuple[str, str], dict[str, Any]] = {}
    for row in results:
        key = (str(row.get("id")), str(row.get("model")))
        if (
            row.get("dataset") == "draw1k"
            and row.get("metadata", {}).get("split") == "test"
            and row.get("model") in models
            and row.get("symcode", {}).get("status") == "ok"
            and key[0] in sources
        ):
            artifacts[key] = row

    common_ids = sorted(
        set.intersection(
            *(
                {uid for uid, model in artifacts if model == candidate}
                for candidate in models
            )
        )
    )
    if sample_size > len(common_ids):
        raise ValueError(f"requested {sample_size} common IDs, only {len(common_ids)} available")
    selected = sorted(random.Random(seed).sample(common_ids, sample_size))
    jobs = []
    for uid in selected:
        source = sources[uid]
        for model in models:
            artifact = artifacts[(uid, model)]
            jobs.append(
                {
                    "id": uid,
                    "generator_model": model,
                    "problem": source["problem"],
                    "gold_equations": list(source.get("gold_equations") or []),
                    "gold_solutions": list(source.get("gold_solutions") or []),
                    "code": artifact["symcode"]["code"],
                    "executed_answer": artifact["symcode"].get("answer", ""),
                }
            )
    return jobs, selected


def choose_math500_wrong_jobs(
    cohort: list[dict[str, Any]],
    sample_size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates = [row for row in cohort if row.get("cohort") == "EXECUTED_WRONG"]
    if sample_size > len(candidates):
        raise ValueError(f"requested {sample_size} executed-wrong cases, only {len(candidates)} available")
    selected_rows = random.Random(seed).sample(sorted(candidates, key=lambda row: row["id"]), sample_size)
    selected_rows.sort(key=lambda row: row["id"])
    jobs = [
        {
            "id": row["id"],
            "generator_model": "gpt-oss:20b",
            "problem": row["problem"],
            "gold_equations": [],
            "gold_solutions": [row["gold_answer"]],
            "code": row["symcode_plus_code"],
            "executed_answer": row["symcode_plus_answer"],
        }
        for row in selected_rows
    ]
    return jobs, [row["id"] for row in selected_rows]


def choose_six_method_wrong_jobs(
    results: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    sample_size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates = [
        row
        for row in results
        if row.get("method") == "symcode_plus"
        and row.get("executed") is True
        and row.get("correct") is False
        and row.get("id") in sources
    ]
    if sample_size > len(candidates):
        raise ValueError(f"requested {sample_size} executed-wrong cases, only {len(candidates)} available")
    selected_rows = random.Random(seed).sample(sorted(candidates, key=lambda row: row["id"]), sample_size)
    selected_rows.sort(key=lambda row: row["id"])
    jobs = []
    for row in selected_rows:
        successful = [
            attempt
            for attempt in row.get("attempts", [])
            if attempt.get("status") == "ok" and isinstance(attempt.get("code"), str)
        ]
        if not successful:
            continue
        source = sources[row["id"]]
        jobs.append(
            {
                "id": row["id"],
                "generator_model": row["model"],
                "problem": source["problem"],
                "gold_equations": [],
                "gold_solutions": [source["answer"]],
                "code": successful[-1]["code"],
                "executed_answer": row.get("answer", ""),
            }
        )
    return jobs, [job["id"] for job in jobs]


def choose_paired_pilot_jobs(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    jobs = [
        {
            "id": row["id"],
            "generator_model": row["model"],
            "problem": row["problem"],
            "gold_equations": list(row["reference_equations"]),
            "gold_solutions": [row["gold_target"]],
            "code": row["code"],
            "executed_answer": row["answer"],
        }
        for row in results
        if row.get("status") == "ok" and isinstance(row.get("code"), str)
    ]
    return jobs, sorted({job["id"] for job in jobs})


def summarize(rows: list[dict[str, Any]], selected_ids: list[str], args: argparse.Namespace) -> dict[str, Any]:
    by_model: dict[str, Counter[str]] = defaultdict(Counter)
    confidence: dict[str, Counter[str]] = defaultdict(Counter)
    errors = Counter()
    for row in rows:
        if row.get("status") != "ok":
            errors[row.get("error", "unknown").split(":", 1)[0]] += 1
            continue
        audit = normalized_audit(row["audit"])
        by_model[row["generator_model"]][audit["label"]] += 1
        confidence[row["generator_model"]][audit["confidence"]] += 1
    return {
        "dataset": "DRAW-1K test" if args.mode == "draw-common" else "MATH-500 executed-wrong diagnostic",
        "sample_size_problems": len(selected_ids),
        "generator_models": list(args.models),
        "judge_model": args.judge_model,
        "seed": args.seed,
        "selected_ids": selected_ids,
        "prompt_sha256": hashlib.sha256(audit_prompt("P", ["E"], "C", "A").encode()).hexdigest(),
        "labels_by_model": {model: dict(by_model[model]) for model in args.models},
        "confidence_by_model": {model: dict(confidence[model]) for model in args.models},
        "errors": dict(errors),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("Son/results/symcode_degro_parallel.jsonl"))
    parser.add_argument("--data", type=Path, default=Path("data/draw1k/draw1k.jsonl"))
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["gpt-oss:20b", "gpt-oss:120b", "gemma4:31b"])
    parser.add_argument("--judge-model", default="gpt-oss:120b")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument(
        "--mode",
        choices=("draw-common", "math500-wrong", "math500-six-method-wrong", "paired-pilot"),
        default="draw-common",
    )
    args = parser.parse_args()

    models = tuple(args.models)
    if args.mode == "draw-common":
        sources = {row["unique_id"]: row for row in load_jsonl(args.data)}
        jobs, selected_ids = choose_jobs(load_jsonl(args.results), sources, models, args.sample_size, args.seed)
    elif args.mode == "math500-wrong":
        jobs, selected_ids = choose_math500_wrong_jobs(load_jsonl(args.results), args.sample_size, args.seed)
        args.models = ["gpt-oss:20b"]
    elif args.mode == "math500-six-method-wrong":
        sources = {row["unique_id"]: row for row in load_jsonl(args.data)}
        jobs, selected_ids = choose_six_method_wrong_jobs(load_jsonl(args.results), sources, args.sample_size, args.seed)
        args.models = sorted({job["generator_model"] for job in jobs})
    else:
        jobs, selected_ids = choose_paired_pilot_jobs(load_jsonl(args.results))
        args.models = sorted({job["generator_model"] for job in jobs})
    done = completed(args.out)
    pending = [job for job in jobs if (job["id"], job["generator_model"]) not in done]
    keys = load_api_keys(args.keys)
    thread_state = local()

    def client() -> OllamaCloudClient:
        current = getattr(thread_state, "client", None)
        if current is None:
            current = OllamaCloudClient(keys, timeout_s=args.timeout)
            thread_state.client = current
        return current

    def run(job: dict[str, Any]) -> dict[str, Any]:
        try:
            response = client().chat(
                args.judge_model,
                [{"role": "user", "content": audit_prompt(job["problem"], job["gold_equations"], job["code"], job["executed_answer"])}],
                format_schema=AUDIT_SCHEMA,
                options={"temperature": 0.0},
                think="medium",
            )
            audit = normalized_audit(json.loads(str(response.get("message", {}).get("content", ""))))
            return {
                "id": job["id"],
                "generator_model": job["generator_model"],
                "executed_answer": job["executed_answer"],
                "gold_solutions": job["gold_solutions"],
                "status": "ok",
                "audit": audit,
            }
        except Exception as exc:
            return {
                "id": job["id"],
                "generator_model": job["generator_model"],
                "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:800]}",
            }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if pending:
        with ThreadPoolExecutor(max_workers=min(args.workers, len(pending))) as pool, args.out.open("a", encoding="utf-8") as stream:
            futures = {pool.submit(run, job): job for job in pending}
            for index, future in enumerate(as_completed(futures), 1):
                row = future.result()
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                print(f"[{index}/{len(pending)}] {row['id']} {row['generator_model']} {row['status']}", flush=True)

    rows = load_jsonl(args.out) if args.out.exists() else []
    summary = summarize(rows, selected_ids, args)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
