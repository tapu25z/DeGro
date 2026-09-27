#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import local
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import Son.run_symcode_parallel as symcode_runner
from targetcheck.providers import OllamaCloudClient, load_api_keys


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def completed(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    return {
        (row["id"], row["model"])
        for row in load_jsonl(path)
        if row.get("status") in {"ok", "error"}
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/paired/mira_confirmatory_remaining_120.jsonl"))
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["gpt-oss:20b", "nemotron-3-nano:30b"])
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--debug-attempts", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()

    candidates = [
        row
        for row in load_jsonl(args.data)
        if row.get("label") == "OMISSION"
        and row.get("difficulty") == 3
        and row.get("missing_constraint")
    ]
    if args.sample_size > len(candidates):
        raise ValueError(f"requested {args.sample_size} cases, only {len(candidates)} available")
    selected = random.Random(args.seed).sample(sorted(candidates, key=lambda row: row["pair_id"]), args.sample_size)
    jobs = [(row, model) for row in selected for model in args.models]
    done = completed(args.out)
    jobs = [(row, model) for row, model in jobs if (row["pair_id"], model) not in done]

    symcode_runner.load_runtime()
    keys = load_api_keys(args.keys)
    thread_state = local()

    def client() -> OllamaCloudClient:
        current = getattr(thread_state, "client", None)
        if current is None:
            current = OllamaCloudClient(keys, timeout_s=args.timeout)
            thread_state.client = current
        return current

    def run(row: dict[str, Any], model: str) -> dict[str, Any]:
        generated = symcode_runner.generate_code(
            client(),
            model,
            symcode_runner.symcode_prompt(row["problem"]),
            args.think,
            args.debug_attempts,
        )
        base_constraints = [constraint["expression"] for constraint in row["spec"]["constraints"]]
        reference = base_constraints + [row["missing_constraint"]["expression"]]
        result = {
            "id": row["pair_id"],
            "family": row["family"],
            "difficulty": row["difficulty"],
            "model": model,
            "problem": row["problem"],
            "gold_target": row["gold_target"],
            "reference_equations": reference,
            "target": row["spec"]["target"],
            "missing_constraint": row["missing_constraint"],
            "status": generated["status"],
            "attempts": generated.get("attempts", []),
        }
        if generated["status"] == "ok":
            result.update(code=generated["code"], answer=generated["answer"])
        return result

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=min(args.workers, len(jobs))) as pool, args.out.open("a", encoding="utf-8") as stream:
        futures = {pool.submit(run, row, model): (row, model) for row, model in jobs}
        for index, future in enumerate(as_completed(futures), 1):
            row, model = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "id": row["pair_id"],
                    "family": row["family"],
                    "difficulty": row["difficulty"],
                    "model": model,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                }
            stream.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            print(f"[{index}/{len(jobs)}] {result['id']} {model} {result['status']}", flush=True)


if __name__ == "__main__":
    main()
