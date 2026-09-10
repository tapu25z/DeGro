#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from math_verify import parse, verify

from targetcheck.providers import OllamaCloudClient, load_api_keys
from targetcheck.symcode_full import SymCodeExecutionError, execute_symcode_full, extract_python_code


SEED = 20260910


def cot_prompt(problem: str) -> str:
    return f"""Solve the following mathematics problem. Think step-by-step and give the final answer in LaTeX boxed form as \\boxed{{answer}}.

# PROBLEM
{problem}
# END PROBLEM"""


def symcode_prompt(problem: str) -> str:
    return f"""You are an expert mathematical reasoner. Your output must be ONLY a single Python code block fenced as ```python ... ``` with no prose before or after.
Inside that single Python script:
1. Import SymPy with `import sympy as sp`
2. Add explicit step-by-step reasoning as comments throughout your code
3. Clearly identify variables, constraints, and goals in comments, and define symbols with appropriate assumptions
4. Show intermediate algebraic manipulations clearly
5. Verify the result: substitute solutions into original equations, check domain constraints, filter invalid solutions, and use assertions for key conditions
6. Convert the final answer to LaTeX when needed and print ONLY it in boxed form, for example `print(r"\\boxed{{" + str(final_answer) + "}}")`

# PROBLEM
{problem}
# END PROBLEM"""


def boxed(text: str) -> str:
    starts = list(re.finditer(r"\\boxed\{", text))
    for start in reversed(starts):
        depth = 1
        index = start.end()
        while index < len(text) and depth:
            depth += (text[index] == "{") - (text[index] == "}")
            index += 1
        if depth == 0:
            return text[start.start():index]
    return text.strip()


def answer_body(text: str) -> str:
    value = boxed(text).strip().strip("$")
    if value.startswith(r"\boxed{") and value.endswith("}"):
        value = value[len(r"\boxed{"):-1]
    value = re.sub(r"\\text\s*\{\s*(?:or|and)\s*\}", ",", value, flags=re.I)
    value = value.replace(r"\quad", ",").replace(";", ",")
    return value


def split_answers(text: str) -> list[str]:
    value = answer_body(text)
    pieces, start, depth = [], 0, 0
    for index, char in enumerate(value):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            pieces.append(value[start:index].strip())
            start = index + 1
    pieces.append(value[start:].strip())
    expanded = []
    for piece in pieces:
        if "=" in piece and not any(operator in piece for operator in ("<=", ">=", r"\le", r"\ge")):
            piece = piece.split("=", 1)[1].strip()
        if r"\pm" in piece:
            expanded.extend((piece.replace(r"\pm", "+").lstrip("+"), piece.replace(r"\pm", "-")))
        else:
            expanded.append(piece)
    return [piece for piece in expanded if piece]


def is_correct(prediction: str, gold_answers: list[str]) -> bool:
    def ensure_boxed(value: str) -> str:
        value = value.strip().strip("$")
        return value if r"\boxed{" in value else r"\boxed{" + value + "}"

    try:
        prediction_parsed = parse(ensure_boxed(prediction))
        if any(verify(parse(ensure_boxed(gold)), prediction_parsed) for gold in gold_answers):
            return True
    except Exception:
        pass
    gold_parts = split_answers(",".join(gold_answers))
    predicted_parts = split_answers(prediction)
    if len(gold_parts) != len(predicted_parts):
        return False
    unmatched = list(predicted_parts)
    for gold in gold_parts:
        for index, predicted in enumerate(unmatched):
            try:
                equal = verify(parse(ensure_boxed(gold)), parse(ensure_boxed(predicted)))
            except Exception:
                equal = gold.replace(" ", "") == predicted.replace(" ", "")
            if equal:
                unmatched.pop(index)
                break
        else:
            return False
    return True


def response_text(response: dict) -> str:
    return str(response.get("message", {}).get("content", ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/olympiadbench/oe_to_maths_en_comp.jsonl"))
    parser.add_argument("--dataset", choices=("olympiadbench", "math500"), default="olympiadbench")
    parser.add_argument("--levels", type=int, nargs="*", default=[])
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("low", "medium", "high"), default="high")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int, default=0)
    parser.add_argument("--accounts-per-worker", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--debug-attempts", type=int, default=2)
    parser.add_argument("--skip-cot", action="store_true")
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.data.read_text().splitlines()]
    if args.dataset == "math500":
        rows = [
            {
                "id": row["unique_id"],
                "question": row["problem"],
                "final_answer": [row["answer"]],
                "is_multiple_answer": False,
                "answer_type": "MATH",
                "subfield": row["subject"],
                "level": row["level"],
            }
            for row in rows
            if not args.levels or int(row["level"]) in args.levels
        ]
    random.Random(args.seed).shuffle(rows)
    rows = rows[: args.limit]
    rows = [row for index, row in enumerate(rows) if index % args.num_shards == args.shard_index]
    completed = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            try:
                completed.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    rows = [row for row in rows if row["id"] not in completed]

    keys = load_api_keys(args.keys)
    offset = args.account_offset % len(keys)
    rotated = keys[offset:] + keys[:offset]
    client = OllamaCloudClient(rotated[: min(args.accounts_per_worker, len(rotated))], timeout_s=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as stream:
        for index, row in enumerate(rows, 1):
            record = {
                "id": row["id"], "subfield": row["subfield"], "answer_type": row["answer_type"],
                "question": row["question"], "gold_answers": row["final_answer"],
                "model": args.model, "think": args.think, "temperature": 0.0, "seed": args.seed,
            }
            if "level" in row:
                record["level"] = row["level"]
            started = time.monotonic()
            if args.skip_cot:
                record.update(cot_status="skipped", cot_correct=False)
            else:
                try:
                    raw = response_text(client.chat(args.model, [{"role": "user", "content": cot_prompt(row["question"])}], options={"temperature": 0.0, "num_predict": 4096}, think=args.think))
                    answer = boxed(raw)
                    record.update(cot_status="ok", cot_raw=raw, cot_answer=answer, cot_correct=is_correct(answer, row["final_answer"]))
                except Exception as exc:
                    record.update(cot_status="error", cot_error=f"{type(exc).__name__}: {str(exc)[:500]}", cot_correct=False)

            messages = [{"role": "user", "content": symcode_prompt(row["question"])}]
            attempts = []
            for attempt in range(args.debug_attempts + 1):
                raw = ""
                try:
                    raw = response_text(client.chat(args.model, messages, options={"temperature": 0.0, "num_predict": 4096}, think=args.think))
                    code = extract_python_code(raw)
                    printed = execute_symcode_full(code)
                    attempts.append({"raw": raw, "code": code, "status": "ok", "output": printed})
                    break
                except Exception as exc:
                    error = f"{type(exc).__name__}: {str(exc)[:600]}"
                    attempts.append({"raw": raw, "status": "error", "error": error})
                    if attempt < args.debug_attempts:
                        messages.extend([
                            {"role": "assistant", "content": raw},
                            {"role": "user", "content": f"Debug the code based on this execution error and return one corrected Python code block only:\n{error}"},
                        ])
            first = attempts[0]
            last = attempts[-1]
            record.update(
                symcode_attempts=attempts,
                symcode_status=first["status"],
                symcode_answer=first.get("output"),
                symcode_correct=first["status"] == "ok" and is_correct(boxed(first["output"]), row["final_answer"]),
                symcode_plus_status=last["status"],
                symcode_plus_answer=last.get("output"),
                symcode_plus_correct=last["status"] == "ok" and is_correct(boxed(last["output"]), row["final_answer"]),
                debug_activated=len(attempts) > 1,
            )
            record["wall_seconds"] = round(time.monotonic() - started, 3)
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            print(f"[{index}/{len(rows)}] id={row['id']} cot={record['cot_correct']} sym={record['symcode_correct']} sym+={record['symcode_plus_correct']}", flush=True)


if __name__ == "__main__":
    main()
