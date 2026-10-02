#!/usr/bin/env python3
"""DeGro variant that replaces Z3 decisions with direct LLM decisions."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from pathlib import Path

from targetcheck.pilot import OUTPUT_SCHEMA, NONUNIQUE_VERDICT, build_prompt, parse_decision, score
from targetcheck.providers import OllamaCloudClient, load_api_keys


STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["DETERMINATE", "AMBIGUOUS", "INCONSISTENT", "UNKNOWN", "NOT_SUPPORTED"],
        }
    },
    "required": ["status"],
    "additionalProperties": False,
}

GATE_SCHEMA = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["ACCEPT", "REJECT"]}},
    "required": ["status"],
    "additionalProperties": False,
}

MIRA360_FILES = (
    Path("data/paired/mira_pilot_80.jsonl"),
    Path("data/paired/mira_heldout_100.jsonl"),
    Path("data/paired/mira_confirmatory_remaining_120.jsonl"),
    Path("data/paired/mira_geometry_60.jsonl"),
)


def spec_text(row: dict) -> str:
    return json.dumps(row["spec"], ensure_ascii=False, indent=2)


def status_prompt(row: dict) -> str:
    return f"""Classify this formal specification.
Return DETERMINATE if it is feasible and all feasible assignments have the same target value.
Return AMBIGUOUS if two feasible assignments can have different target values.
Return INCONSISTENT if it has no feasible assignment, NOT_SUPPORTED if you cannot interpret it, otherwise UNKNOWN.
Use only the ModelSpec; do not add facts from the source problem.

ModelSpec:
{spec_text(row)}"""


def repair_prompt(row: dict) -> str:
    return build_prompt("nonunique_grounding", row).replace(
        NONUNIQUE_VERDICT,
        "\n\nLLM verifier verdict: the target is not uniquely determined by the current constraints.",
    )


def gate_prompt(row: dict, proposal: dict) -> str:
    return f"""Validate this proposed repair.
Return ACCEPT only if the cited source directly supports the constraint, the repaired specification is feasible, the constraint is non-redundant, and the target becomes determinate. Otherwise return REJECT.

Original problem:
{row['problem']}

Current ModelSpec:
{spec_text(row)}

Proposed repair:
{json.dumps(proposal, ensure_ascii=False, indent=2)}"""


def call_json(client, model, think, prompt, schema) -> dict:
    response = client.chat(
        model,
        [{"role": "user", "content": prompt}],
        format_schema=schema,
        options={"temperature": 1.0},
        think=think,
    )
    content = response["message"]["content"].strip()
    allowed = schema.get("properties", {}).get("status", {}).get("enum", [])
    if content in allowed:
        return {"status": content}
    candidates = [content]
    candidates.extend(reversed(re.findall(r"```(?:json)?\s*(.*?)\s*```", content, re.I | re.S)))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise ValueError(f"invalid JSON response: {content[:200]}")


def run_pair(cases, keys, key_offset, model, think, timeout):
    client = OllamaCloudClient(keys[key_offset:] + keys[:key_offset], timeout_s=timeout)
    stage = "status"
    try:
        predicted_status = call_json(client, model, think, status_prompt(cases[0]), STATUS_SCHEMA)["status"]
        decisions = []
        for row in cases:
            output = {"decision": "ABSTAIN", "source_span": None, "constraint": None}
            gate = None
            if predicted_status == "AMBIGUOUS":
                stage = f"repair:{row['label']}"
                response = client.chat(
                    model,
                    [{"role": "user", "content": repair_prompt(row)}],
                    format_schema=OUTPUT_SCHEMA,
                    options={"temperature": 1.0},
                    think=think,
                )
                output = parse_decision(response["message"]["content"])
                if output["decision"] == "ADD_CONSTRAINT":
                    stage = f"gate:{row['label']}"
                    gate = call_json(client, model, think, gate_prompt(row, output), GATE_SCHEMA)
            decisions.append((output, gate))
        return predicted_status, decisions, None
    except Exception as exc:
        return None, None, (stage, type(exc).__name__, str(exc)[:500])


def main() -> None:
    parser = argparse.ArgumentParser()
    data_group = parser.add_mutually_exclusive_group(required=True)
    data_group.add_argument("--data", type=Path)
    data_group.add_argument("--mira360", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("low", "medium", "high", "true", "false"), default="medium")
    parser.add_argument("--limit-pairs", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.num_shards < 1 or not 0 <= args.shard_index < args.num_shards:
        parser.error("shard-index must be in [0, num-shards)")
    if args.workers < 1:
        parser.error("workers must be positive")

    think = {"true": True, "false": False}.get(args.think, args.think)
    data_files = MIRA360_FILES if args.mira360 else (args.data,)
    rows = [json.loads(line) for path in data_files for line in path.read_text().splitlines()]
    pair_ids = list(dict.fromkeys(row["pair_id"] for row in rows))
    if args.limit_pairs:
        pair_ids = pair_ids[: args.limit_pairs]
    selected = {
        pair_id for index, pair_id in enumerate(pair_ids)
        if index % args.num_shards == args.shard_index
    }
    rows = [row for row in rows if row["pair_id"] in selected]

    grouped = {}
    for row in rows:
        grouped.setdefault(row["pair_id"], []).append(row)

    keys = load_api_keys(args.keys)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool, args.out.open("w") as stream:
        futures = {
            pool.submit(run_pair, cases, keys, index % len(keys), args.model, think, args.timeout):
                (pair_id, cases)
            for index, (pair_id, cases) in enumerate(grouped.items())
        }
        for future in as_completed(futures):
            pair_id, cases = futures[future]
            predicted_status, decisions, error = future.result()
            pair_records = []
            try:
                if error is not None:
                    raise RuntimeError(error[2])
                for row, (output, gate) in zip(cases, decisions):
                    # Z3 is the Table-2 evaluation oracle; only the LLM controls the flow.
                    result = score(row, output)
                    if output["decision"] == "ADD_CONSTRAINT" and gate.get("status") != "ACCEPT":
                        result["correct_repair"] = False
                        result["correct"] = False
                    pair_records.append({
                        "model": args.model, "temperature": 1.0, "think": think,
                        "pair_id": pair_id, "family": row["family"],
                        "difficulty": row["difficulty"], "label": row["label"],
                        "method": "llm_degro", "status": "ok",
                        "predicted_status": predicted_status, "output": output,
                        "llm_gate": gate, "score": result,
                    })
            except Exception as exc:
                stage = error[0] if error is not None else "score"
                error_type = error[1] if error is not None else type(exc).__name__
                pair_records = [{
                    "model": args.model, "temperature": 1.0, "think": think,
                    "pair_id": pair_id, "family": row["family"],
                    "difficulty": row["difficulty"], "label": row["label"],
                    "method": "llm_degro", "status": "error",
                    "error_stage": stage, "error_type": error_type,
                    "error": str(exc)[:500],
                } for row in cases]
            for record in pair_records:
                stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            stream.flush()
            last = pair_records[-1]
            detail = f" ({last['error_stage']}: {last['error']})" if last["status"] == "error" else ""
            print(f"{pair_id}: {last['status']}{detail}", flush=True)


if __name__ == "__main__":
    main()
