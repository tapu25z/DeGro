#!/usr/bin/env python3
"""Run the SymCode -> DeGro pipeline against a local Ollama server.

This entry point is intended for a GPU host such as Vast.ai.  It reuses the
project's existing prompts, SymCode sandbox, Z3 determinacy checker, grounded
repair gate, dataset loaders, scoring, and resumable JSONL format.  Unlike the
cloud runner, it requires no API keys and never sends an Authorization header.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Son import run_symcode_parallel as pipeline  # noqa: E402


class OllamaLocalError(RuntimeError):
    """Raised when the local Ollama HTTP API is unavailable or rejects a call."""


class OllamaLocalClient:
    """Small no-auth client compatible with the project's pipeline interface."""

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        timeout_s: float = 600.0,
        num_ctx: int = 8192,
        keep_alive: str = "30m",
        opener: Any = urllib.request.urlopen,
    ) -> None:
        self.host = host.rstrip("/")
        self.timeout_s = timeout_s
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self._opener = opener

    def _request(
        self, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.host + path,
            data=body,
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json", "User-Agent": "degro-vastai/1"},
        )
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise OllamaLocalError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise OllamaLocalError(
                f"cannot reach Ollama at {self.host}: {type(exc).__name__}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaLocalError("Ollama returned invalid JSON") from exc

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        format_schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        think: str | bool | None = None,
    ) -> dict[str, Any]:
        merged_options = {"num_ctx": self.num_ctx, **(options or {})}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": merged_options,
            "keep_alive": self.keep_alive,
        }
        if format_schema is not None:
            payload["format"] = format_schema
        if think is not None:
            payload["think"] = think
        return self._request("/api/chat", payload)

    def list_models(self) -> dict[str, Any]:
        return self._request("/api/tags")


def model_names(response: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in response.get("models", []):
        if not isinstance(item, dict):
            continue
        for field in ("name", "model"):
            value = item.get(field)
            if isinstance(value, str):
                names.add(value)
    return names


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_") or "model"


def parse_think(value: str) -> str | bool:
    if value == "off":
        return False
    if value == "on":
        return True
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SymCode + DeGro with a local Ollama model on a GPU host."
    )
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen3:8b"))
    parser.add_argument(
        "--host", default=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=tuple(pipeline.DATASETS) + ("all",),
        default=["all"],
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--think", choices=("off", "on", "low", "medium", "high"), default="off"
    )
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--debug-attempts", type=int, default=2)
    parser.add_argument("--skip-model-check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be positive")
    if args.num_ctx < 2048:
        raise SystemExit("--num-ctx must be at least 2048")

    names = (
        tuple(pipeline.DATASETS)
        if "all" in args.datasets
        else tuple(dict.fromkeys(args.datasets))
    )
    examples = pipeline.load_examples(names, args.limit)
    output = args.out or (
        Path(__file__).resolve().parent
        / "results"
        / f"{safe_model_name(args.model)}_symcode_degro.jsonl"
    )
    done = pipeline.completed_keys(output)
    jobs = [
        pipeline.Job(example, args.model)
        for example in examples
        if (example.dataset, example.uid, args.model) not in done
    ]
    summary = {
        "host": args.host,
        "model": args.model,
        "datasets": {
            name: sum(example.dataset == name for example in examples) for name in names
        },
        "workers": args.workers,
        "num_ctx": args.num_ctx,
        "think": args.think,
        "completed": len(done),
        "pending_jobs": len(jobs),
        "output": str(output),
    }
    print(json.dumps(summary, indent=2), flush=True)
    if args.dry_run or not jobs:
        return

    health_client = OllamaLocalClient(
        args.host, args.timeout, args.num_ctx, args.keep_alive
    )
    available = model_names(health_client.list_models())
    if not args.skip_model_check and args.model not in available:
        choices = ", ".join(sorted(available)) or "none"
        raise SystemExit(
            f"model {args.model!r} is not installed in Ollama; available: {choices}. "
            f"Run: ollama pull {args.model}"
        )

    pipeline.load_runtime()
    think = parse_think(args.think)
    solver = pipeline.SolverBridge()
    thread_state = threading.local()

    def client_for_thread() -> OllamaLocalClient:
        client = getattr(thread_state, "client", None)
        if client is None:
            client = OllamaLocalClient(
                args.host, args.timeout, args.num_ctx, args.keep_alive
            )
            thread_state.client = client
        return client

    def worker(job: pipeline.Job) -> dict[str, Any]:
        return pipeline.run_job(
            job, client_for_thread(), solver, think, args.debug_attempts
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ThreadPoolExecutor(
            max_workers=min(args.workers, len(jobs)), thread_name_prefix="ollama"
        ) as pool:
            futures = {pool.submit(worker, job): job for job in jobs}
            with output.open("a", encoding="utf-8") as stream:
                for index, future in enumerate(as_completed(futures), 1):
                    job = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = {
                            "dataset": job.example.dataset,
                            "id": job.example.uid,
                            "model": job.model,
                            "run_status": "error",
                            "decision": "WORKER_ERROR",
                            "error": f"{type(exc).__name__}: {str(exc)[:800]}",
                        }
                    if record.get("run_status") == "ok" and record.get("final_answer"):
                        record["correct"] = pipeline.score_answer(
                            record["final_answer"], record["gold_answers"]
                        )
                    stream.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            default=str,
                        )
                        + "\n"
                    )
                    stream.flush()
                    print(
                        f"[{index}/{len(jobs)}] {record['dataset']} {record['id']} "
                        f"{record['model']} -> {record.get('decision')}",
                        flush=True,
                    )
    finally:
        solver.close()


if __name__ == "__main__":
    main()
