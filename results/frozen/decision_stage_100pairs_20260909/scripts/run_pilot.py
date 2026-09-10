#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from targetcheck.pilot import METHODS, OUTPUT_SCHEMA, build_prompt, parse_decision, prompt_hash, score
from targetcheck.providers import OllamaCloudClient, load_api_keys


def load_completed(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    completed = set()
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row.get("status") == "ok":
            completed.add((row["pair_id"], row["label"], row["method"]))
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/paired/mira_pilot_80.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("results/raw/gpt_oss_20b_pilot.jsonl"))
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--limit-pairs", type=int)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int)
    parser.add_argument("--resume-from", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.data.read_text().splitlines()]
    if args.limit_pairs:
        ids = list(dict.fromkeys(row["pair_id"] for row in rows))[: args.limit_pairs]
        rows = [row for row in rows if row["pair_id"] in ids]
    if not 0 <= args.shard_index < args.num_shards:
        raise SystemExit("shard-index must be in [0, num-shards)")
    all_ids = list(dict.fromkeys(row["pair_id"] for row in rows))
    shard_ids = {pair_id for index, pair_id in enumerate(all_ids) if index % args.num_shards == args.shard_index}
    rows = [row for row in rows if row["pair_id"] in shard_ids]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    completed = load_completed(args.out)
    for checkpoint in args.resume_from:
        completed.update(load_completed(checkpoint))
    keys = load_api_keys(args.keys)
    offset = (args.account_offset if args.account_offset is not None else args.shard_index) % len(keys)
    keys = keys[offset:] + keys[:offset]
    client = OllamaCloudClient(keys, timeout_s=180)
    config = {"model": args.model, "temperature": 1.0, "think": "medium", "prompt_hash": prompt_hash()}
    total = len(rows) * len(args.methods)
    relevant = {(row["pair_id"], row["label"], method) for row in rows for method in args.methods}
    completed.intersection_update(relevant)
    done = len(completed)
    with args.out.open("a") as stream:
        for row in rows:
            for method in args.methods:
                key = (row["pair_id"], row["label"], method)
                if key in completed:
                    continue
                started = time.monotonic()
                record = {**config, "pair_id": row["pair_id"], "family": row["family"], "difficulty": row["difficulty"], "label": row["label"], "method": method}
                content = ""
                try:
                    response = client.chat(
                        args.model,
                        [{"role": "user", "content": build_prompt(method, row)}],
                        format_schema=OUTPUT_SCHEMA,
                        options={"temperature": 1.0},
                        think="medium",
                    )
                    content = response.get("message", {}).get("content", "")
                    output = parse_decision(content)
                    record.update({"status": "ok", "output": output, "score": score(row, output)})
                    for field in ("prompt_eval_count", "eval_count", "total_duration", "load_duration"):
                        if field in response:
                            record[field] = response[field]
                    record["account_attempts"] = [attempt.__dict__ for attempt in client.last_attempts]
                except Exception as exc:
                    record.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500], "raw_content": content[:2000]})
                record["wall_seconds"] = round(time.monotonic() - started, 3)
                stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                stream.flush()
                done += 1
                print(f"[{done}/{total}] {row['pair_id']} {row['label']} {method} {record['status']}", flush=True)


if __name__ == "__main__":
    main()
