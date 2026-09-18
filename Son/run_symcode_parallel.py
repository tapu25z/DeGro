#!/usr/bin/env python3
"""Run the SymCode -> DeGro instruction flow across the project datasets.

Configuration is read from ``.env`` without adding secrets to ``os.environ``.
Supported forms are ``OLLAMA_API_KEY[_N]=...``, ``OLLAMA_API_KEYS=k1,k2``,
or the repository's existing ``label - key`` lines. Models come from
``OLLAMA_MODELS=model1,model2`` or ``--models``.

Examples:
    conda run -n Degro python Son/run_symcode_parallel.py --dry-run
    conda run -n Degro python Son/run_symcode_parallel.py --limit 2
    conda run -n Degro python Son/run_symcode_parallel.py --datasets math500 alg514
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MODELS = ("gpt-oss:20b", "gpt-oss:120b", "gemma4:31b")
DATASETS = {
    "alg514": ROOT / "data/alg514/alg514.jsonl",
    "draw1k": ROOT / "data/draw1k/draw1k.jsonl",
    "math500": ROOT / "data/math500/test.jsonl",
    "mira_pilot": ROOT / "data/paired/mira_pilot_80.jsonl",
    "mira_heldout": ROOT / "data/paired/mira_heldout_100.jsonl",
    "mira_confirmatory": ROOT / "data/paired/mira_confirmatory_remaining_120.jsonl",
    "olympiadbench": ROOT / "data/olympiadbench/oe_to_maths_en_comp.jsonl",
}

_score_lock = threading.Lock()


def load_runtime() -> None:
    """Import solver/LLM dependencies only when an actual run starts."""
    global DRAW_FORMALIZATION_SCHEMA, REPAIR_SCHEMA
    global OllamaCloudClient, apply_repair, base_spec, boxed, check_joint
    global execute_symcode_full, extract_python_code, is_correct, parse_object
    global repair_prompt, symcode_prompt

    from scripts.run_draw1k_natural import (
        DRAW_FORMALIZATION_SCHEMA,
        base_spec,
        check_joint,
    )
    from scripts.run_math500_natural import (
        REPAIR_SCHEMA,
        apply_repair,
        parse_object,
        repair_prompt,
    )
    from scripts.run_olympiadbench_symcode import boxed, is_correct, symcode_prompt
    from targetcheck.providers import OllamaCloudClient
    from targetcheck.symcode_full import execute_symcode_full, extract_python_code


@dataclass(frozen=True)
class Example:
    dataset: str
    source: str
    uid: str
    problem: str
    gold_answers: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Job:
    example: Example
    model: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.example.dataset, self.example.uid, self.model


def _solver_task(function: Any, args: tuple[Any, ...]) -> tuple[bool, Any]:
    """Keep Z3 exceptions and object destruction inside the solver thread."""
    try:
        return True, function(*args)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:1200]}"


class SolverBridge:
    """Run every Z3 operation on one dedicated thread.

    The z3-solver ctypes bindings can segfault when objects that share the
    global context are created and finalized concurrently on worker threads.
    Ollama calls remain parallel; only the short solver sections are serialized.
    """

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="z3")

    def call(self, function: Any, *args: Any) -> Any:
        ok, value = self._pool.submit(_solver_task, function, args).result()
        if not ok:
            raise RuntimeError(value)
        return value

    def close(self) -> None:
        self._pool.shutdown(wait=True)


def split_csv(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        part.strip() for value in values for part in value.split(",") if part.strip()
    )


def read_env(path: Path) -> tuple[dict[str, str], tuple[str, ...]]:
    """Read runner settings and keys, including the legacy labelled-key format."""
    if not path.exists():
        return {}, ()
    settings: dict[str, str] = {}
    keys: list[str] = []
    setting_names = {"OLLAMA_MODELS", "OLLAMA_HOST", "OLLAMA_WORKERS"}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip("'\"")
            if name in setting_names:
                settings[name] = value
            elif name == "OLLAMA_API_KEYS":
                keys.extend(split_csv([value]))
            elif name.startswith("OLLAMA_API_KEY") and value:
                keys.append(value)
            elif value:
                # Preserve compatibility with arbitrary NAME=key labels.
                keys.append(value)
        else:
            value = line.split()[-1].strip("'\"")
            if value:
                keys.append(value)
    return settings, tuple(dict.fromkeys(keys))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected an object")
        rows.append(value)
    return rows


def normalize(dataset: str, path: Path, row: dict[str, Any]) -> Example:
    if dataset in {"alg514", "draw1k"}:
        uid = str(row["unique_id"])
        problem = str(row["problem"])
        gold = tuple(str(value) for value in row["gold_solutions"])
    elif dataset == "math500":
        uid = str(row["unique_id"])
        problem = str(row["problem"])
        gold = (str(row["answer"]),)
    elif dataset.startswith("mira_"):
        uid = f"{row['pair_id']}:{row['label']}"
        problem = str(row["problem"])
        gold = (str(row["gold_target"]),)
    elif dataset == "olympiadbench":
        uid = str(row["id"])
        problem = str(row["question"])
        gold = tuple(str(value) for value in row["final_answer"])
    else:
        raise ValueError(f"unsupported dataset: {dataset}")
    metadata_keys = (
        "split",
        "subject",
        "subfield",
        "level",
        "family",
        "difficulty",
        "label",
        "answer_type",
    )
    metadata = {key: row[key] for key in metadata_keys if key in row}
    return Example(dataset, str(path.relative_to(ROOT)), uid, problem, gold, metadata)


def load_examples(names: tuple[str, ...], limit: int | None) -> list[Example]:
    examples = []
    for name in names:
        path = DATASETS[name]
        if not path.exists():
            raise FileNotFoundError(path)
        rows = load_jsonl(path)
        if limit is not None:
            rows = rows[:limit]
        examples.extend(normalize(name, path, row) for row in rows)
    return examples


def response_text(response: dict[str, Any]) -> str:
    return str(response.get("message", {}).get("content", ""))


def parse_object_flexible(content: str) -> dict[str, Any]:
    """Parse JSON from strict output, fenced output, or surrounding prose."""
    try:
        return parse_object(content)
    except ValueError as original:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", content):
            try:
                value, _ = decoder.raw_decode(content[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise ValueError("response does not contain a JSON object") from original


def structured_object(
    client: OllamaCloudClient,
    model: str,
    prompt: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Request structured output with one format-independent retry."""
    errors = []
    for attempt in range(2):
        retry_note = (
            ""
            if attempt == 0
            else "\n\nReturn only the JSON object. Do not use markdown or explanatory prose."
        )
        content = ""
        try:
            response = client.chat(
                model,
                [{"role": "user", "content": prompt + retry_note}],
                format_schema=schema if attempt == 0 else None,
                options={"temperature": 0.0, "num_predict": 3072},
                think=False,
            )
            content = response_text(response)
            return parse_object_flexible(content)
        except Exception as exc:
            snippet = content.strip().replace("\n", " ")[:240]
            suffix = f"; response={snippet!r}" if snippet else ""
            errors.append(f"{type(exc).__name__}: {str(exc)[:300]}{suffix}")
    raise ValueError("structured output failed after retry (" + "; ".join(errors) + ")")


def extract_code_flexible(content: str) -> str:
    """Accept the requested Python fence plus common harmless wrapper variants."""
    try:
        return extract_python_code(content)
    except Exception as original:
        blocks = re.findall(r"```(?:python|py)?\s*(.*?)\s*```", content, re.I | re.S)
        if blocks:
            return blocks[-1]
        try:
            value = parse_object_flexible(content)
        except ValueError:
            value = None
        if isinstance(value, dict) and isinstance(value.get("code"), str):
            return value["code"]
        candidate = content.strip()
        if "sympy" in candidate and "print(" in candidate:
            return candidate
        raise original


def normalized_answer(answer: str) -> str:
    """Normalize common executable-output notation before math verification."""
    return re.sub(r"(?<!\\)\bpi\b", r"\\pi", answer)


def score_answer(answer: str | None, gold_answers: tuple[str, ...] | list[str]) -> bool:
    if not answer:
        return False
    # math_verify's parser is not thread-safe; serialize only this short step.
    with _score_lock:
        return is_correct(boxed(normalized_answer(answer)), list(gold_answers))


def degro_prompt(problem: str, code: str) -> str:
    return f"""Build a source-grounded Z3-compatible model for this mathematical problem and its generated SymCode artifact.

Original problem:
{problem}

Generated SymCode:
```python
{code}
```

The original problem is authoritative. Use the code only to identify candidate variables and operations; do not copy unsupported assumptions or insert its computed answer as a constraint.

Return exactly one JSON object matching the supplied schema. Use SUPPORTED only when every requested numeric quantity can be represented with one or two Int/Real variables, arithmetic constraints, and scalar target expressions. Encode every target-relevant source fact. Use only Python-style ==, !=, <, <=, >, >=, +, -, *, /, %, **, and/or; never use function calls in expressions. Every EXPLICIT_TEXT constraint must quote an exact contiguous source_span. DOMAIN_SEMANTICS is allowed only for conventional mathematical domains and must have a null source_span.

SUPPORTED example:
{{"status":"SUPPORTED","variables":[{{"name":"x","sort":"Real","lower":null,"upper":null,"values":null}}],"constraints":[{{"id":"c1","expression":"x == 3","source_span":"x is 3","provenance":"EXPLICIT_TEXT"}}],"targets":["x"]}}

For NOT_SUPPORTED return empty variables, constraints, and targets."""


def grounded_repair_prompt(
    problem: str, code: str, spec: Any, targets: list[str], result: Any
) -> str:
    evidence = {
        "targets": targets,
        "ambiguous_target": result.ambiguous_target,
        "witness_1": result.witness_1,
        "witness_2": result.witness_2,
    }
    return (
        repair_prompt(problem, spec, determinacy_signal=True)
        + f"""

Generated SymCode:
```python
{code}
```

DeGro evidence:
{json.dumps(evidence, ensure_ascii=False, default=str)}

The evidence only proves ambiguity; it does not license a repair. Add a constraint only when the original problem explicitly or conventionally supports it."""
    )


def code_repair_prompt(problem: str, code: str, repair: dict[str, Any]) -> str:
    return (
        symcode_prompt(problem)
        + f"""

The previous executable artifact was:
```python
{code}
```

DeGro accepted this source-grounded missing constraint:
{repair.get("constraint")}

Regenerate the complete script so it encodes that constraint. Return one Python code block only."""
    )


def generate_code(
    client: OllamaCloudClient,
    model: str,
    prompt: str,
    think: str,
    debug_attempts: int,
) -> dict[str, Any]:
    messages = [{"role": "user", "content": prompt}]
    attempts = []
    for attempt in range(debug_attempts + 1):
        raw = ""
        try:
            raw = response_text(
                client.chat(
                    model,
                    messages,
                    options={"temperature": 0.0, "num_predict": 4096},
                    think=think,
                )
            )
            code = extract_code_flexible(raw)
            answer = execute_symcode_full(code)
            attempts.append({"status": "ok", "code": code, "answer": answer})
            return {
                "status": "ok",
                "code": code,
                "answer": answer,
                "attempts": attempts,
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:600]}"
            attempts.append({"status": "error", "error": error, "raw": raw[:4000]})
            if attempt < debug_attempts:
                messages.extend(
                    [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": f"Fix this execution error. Return one corrected Python code block only.\n{error}",
                        },
                    ]
                )
    return {"status": "error", "attempts": attempts}


def check_fields(result: Any) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "values": list(result.values),
        "ambiguous_target": result.ambiguous_target,
        "witness_1": result.witness_1,
        "witness_2": result.witness_2,
        "reason": result.reason,
    }


def run_job(
    job: Job,
    client: OllamaCloudClient,
    solver: SolverBridge,
    think: str,
    debug_attempts: int,
) -> dict[str, Any]:
    started = time.monotonic()
    example = job.example
    record: dict[str, Any] = {
        "dataset": example.dataset,
        "source": example.source,
        "id": example.uid,
        "model": job.model,
        "problem": example.problem,
        "gold_answers": list(example.gold_answers),
        "metadata": example.metadata,
    }
    try:
        symcode = generate_code(
            client, job.model, symcode_prompt(example.problem), think, debug_attempts
        )
        record["symcode"] = symcode
        if symcode["status"] != "ok":
            record.update(
                run_status="ok",
                decision="ABSTAIN",
                abstain_reason="SYMCODE_GENERATION_FAILED",
                final_answer=None,
                correct=False,
            )
            return record

        try:
            formalization = structured_object(
                client,
                job.model,
                degro_prompt(example.problem, symcode["code"]),
                DRAW_FORMALIZATION_SCHEMA,
            )
        except Exception as exc:
            record.update(
                run_status="ok",
                decision="NO_CERTIFICATE",
                certificate_error=f"{type(exc).__name__}: {str(exc)[:1200]}",
                final_answer=None,
                correct=False,
            )
            return record
        record["formalization"] = formalization
        if formalization.get("status") != "SUPPORTED" or not formalization.get(
            "targets"
        ):
            record.update(
                run_status="ok",
                decision="NO_CERTIFICATE",
                final_answer=None,
                correct=False,
            )
            return record

        targets = list(formalization["targets"])
        initial = solver.call(check_joint, formalization)
        record["degro_initial"] = check_fields(initial)
        final_answer = symcode["answer"]
        if initial.status.value == "DETERMINATE":
            decision = "ACCEPT"
        elif initial.status.value == "AMBIGUOUS":
            spec = base_spec(formalization)
            try:
                repair = structured_object(
                    client,
                    job.model,
                    grounded_repair_prompt(
                        example.problem, symcode["code"], spec, targets, initial
                    ),
                    REPAIR_SCHEMA,
                )
            except Exception as exc:
                record.update(
                    run_status="ok",
                    decision="ABSTAIN",
                    abstain_reason="REPAIR_OUTPUT_INVALID",
                    repair_error=f"{type(exc).__name__}: {str(exc)[:1200]}",
                    final_answer=None,
                    correct=False,
                )
                return record
            repaired_spec, accepted, reason = solver.call(
                apply_repair, example.problem, spec, repair
            )
            record["repair"] = {
                "proposal": repair,
                "accepted": accepted,
                "reason": reason,
            }
            if not accepted:
                decision = "ABSTAIN"
            else:
                final_check = solver.call(check_joint, repaired_spec, targets)
                record["degro_final"] = check_fields(final_check)
                if final_check.status.value != "DETERMINATE":
                    decision = "ABSTAIN"
                else:
                    repaired_code = generate_code(
                        client,
                        job.model,
                        code_repair_prompt(example.problem, symcode["code"], repair),
                        think,
                        debug_attempts,
                    )
                    record["repaired_symcode"] = repaired_code
                    if repaired_code["status"] == "ok":
                        final_answer = repaired_code["answer"]
                        decision = "REPAIRED"
                    else:
                        decision = "ABSTAIN"
        else:
            decision = "NO_CERTIFICATE"

        record.update(
            run_status="ok",
            decision=decision,
            final_answer=final_answer if decision in {"ACCEPT", "REPAIRED"} else None,
            # Scored by the main thread: math_verify is not worker-thread safe.
            correct=None if decision in {"ACCEPT", "REPAIRED"} else False,
        )
    except Exception as exc:
        record.update(
            run_status="error",
            decision="PIPELINE_ERROR",
            error=f"{type(exc).__name__}: {str(exc)[:800]}",
        )
    finally:
        record["wall_seconds"] = round(time.monotonic() - started, 3)
    return record


def completed_keys(path: Path) -> set[tuple[str, str, str]]:
    done = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("run_status") == "ok":
                done.add((row["dataset"], str(row["id"]), row["model"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return done


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel multi-model SymCode + DeGro runner"
    )
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--datasets", nargs="+", choices=tuple(DATASETS) + ("all",), default=["all"]
    )
    parser.add_argument(
        "--models", nargs="+", help="Space- or comma-separated Ollama model names"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "Son/results/symcode_degro_parallel.jsonl",
    )
    parser.add_argument(
        "--limit", type=int, help="Maximum rows per dataset; default is every row"
    )
    parser.add_argument("--workers", type=int)
    parser.add_argument("--think", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--debug-attempts", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings, keys = read_env(args.env)
    models = (
        split_csv(args.models)
        if args.models
        else split_csv([settings.get("OLLAMA_MODELS", "")])
    )
    models = models or DEFAULT_MODELS
    names = (
        tuple(DATASETS)
        if "all" in args.datasets
        else tuple(dict.fromkeys(args.datasets))
    )
    examples = load_examples(names, args.limit)
    done = completed_keys(args.out)
    jobs = [
        Job(example, model)
        for example in examples
        for model in models
        if (example.dataset, example.uid, model) not in done
    ]
    configured_workers = args.workers or int(settings.get("OLLAMA_WORKERS", "0") or 0)
    workers = configured_workers or min(8, len(keys) or 1)

    summary = {
        "datasets": {
            name: sum(example.dataset == name for example in examples) for name in names
        },
        "models": list(models),
        "keys": len(keys),
        "workers": workers,
        "completed": len(done),
        "pending_jobs": len(jobs),
        "output": str(args.out),
    }
    print(json.dumps(summary, indent=2))
    if args.dry_run or not jobs:
        return
    if not keys:
        raise SystemExit(f"no Ollama API keys found in {args.env}")
    if workers < 1:
        raise SystemExit("--workers must be positive")
    load_runtime()

    host = settings.get("OLLAMA_HOST", "https://ollama.com")
    thread_state = threading.local()
    client_index = itertools.count()
    client_lock = threading.Lock()

    def client_for_thread() -> OllamaCloudClient:
        client = getattr(thread_state, "client", None)
        if client is not None:
            return client
        with client_lock:
            offset = next(client_index) % len(keys)
        rotated = keys[offset:] + keys[:offset]
        client = OllamaCloudClient(rotated, host=host, timeout_s=args.timeout)
        thread_state.client = client
        return client

    solver = SolverBridge()

    def worker(job: Job) -> dict[str, Any]:
        return run_job(
            job, client_for_thread(), solver, args.think, args.debug_attempts
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ThreadPoolExecutor(
            max_workers=min(workers, len(jobs)), thread_name_prefix="symcode"
        ) as pool:
            futures = {pool.submit(worker, job): job for job in jobs}
            with args.out.open("a", encoding="utf-8") as stream:
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
                        record["correct"] = score_answer(
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
