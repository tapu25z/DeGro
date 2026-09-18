#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import time
from pathlib import Path

try:
    from scripts.run_math500_natural import parse_object
except ModuleNotFoundError:
    from run_math500_natural import parse_object
from targetcheck.error_taxonomy import ErrorLabel
from targetcheck.providers import OllamaCloudClient, load_api_keys


ANNOTATION_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_label": {"type": "string", "enum": [label.value for label in ErrorLabel if label != ErrorLabel.UNSURE]},
        "target_critical_underformalization": {"type": "boolean"},
        "evidence": {"type": "string"},
        "notes": {"type": "string"},
        "confidence": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
    },
    "required": ["primary_label", "target_critical_underformalization", "evidence", "notes", "confidence"],
    "additionalProperties": False,
}


def annotation_prompt(item: dict) -> str:
    return f"""Act as a careful research annotation assistant. Compare the generated mathematical formalization with the complete problem and reference solution. Judge semantic faithfulness, not merely whether the final number happens to match.

Problem:
{item['problem']}

Reference solution:
{item['reference_solution']}

Reference answer:
{item['reference_answer']}

Generated formalization:
{json.dumps(item['generated_formalization'], ensure_ascii=False, indent=2)}

Assign exactly one primary label:
- CORRECT: faithfully represents the target-relevant task.
- MISSING_CONSTRAINT: a source-supported condition whose omission can change the requested target is absent.
- WRONG_CONSTRAINT: an encoded relation mistranslates the source.
- EXTRA_CONSTRAINT: an unsupported assumption was added.
- WRONG_DOMAIN: a sort or bound changes feasible solutions.
- WRONG_TARGET: the target expression does not represent the requested quantity.
- COMPUTATIONAL_ERROR: the representation is faithful but downstream computation is wrong.
- OTHER: another error, including a non-target-critical omission or a task outside the declared scalar-answer representation.

Set target_critical_underformalization=true only for MISSING_CONSTRAINT. Give specific evidence identifying the relevant source fact and generated expression. Use LOW confidence whenever the primary label is debatable. Do not infer or mention any hidden solver verdict or repair outcome.

Return exactly one JSON object and no Markdown or prose outside it. Use exactly these keys:
{{"primary_label":"WRONG_TARGET","target_critical_underformalization":false,"evidence":"specific comparison of source and formalization","notes":"brief optional note","confidence":"HIGH"}}"""


def parse_proposal(raw_content: object) -> tuple[dict, list[str]]:
    normalizations = []
    if isinstance(raw_content, dict):
        proposal = dict(raw_content)
    else:
        text = str(raw_content)
        try:
            proposal = parse_object(text)
        except ValueError:
            # Some hosted models emit LaTeX backslashes without JSON escaping.
            # Preserve quote escapes, but escape every mathematical backslash;
            # LaTeX commands such as \frac otherwise collide with JSON's \f.
            quote_escape = "__TARGETCHECK_ESCAPED_QUOTE__"
            repaired = text.replace(r'\"', quote_escape).replace("\\", "\\\\").replace(quote_escape, r'\"')
            proposal = parse_object(repaired)
            normalizations.append("escaped_invalid_json_backslashes")
    missing = proposal.get("primary_label") == "MISSING_CONSTRAINT"
    if proposal.get("target_critical_underformalization") is not missing:
        proposal["target_critical_underformalization"] = missing
        proposal["confidence"] = "LOW"
        normalizations.append("aligned_primary_subset_boolean_with_label")
    return proposal, normalizations


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate blinded AI label proposals for human verification.")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keys", type=Path, default=Path("api.txt"))
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--think", choices=("none", "low", "medium", "high"), default="low")
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--account-offset", type=int)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.packet.read_text().splitlines()]
    rows = [row for index, row in enumerate(rows) if index % args.num_shards == args.shard_index]
    if args.limit is not None:
        rows = rows[: args.limit]
    completed = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            try:
                row = json.loads(line)
                if row.get("status") == "ok":
                    completed.add(row["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    keys = load_api_keys(args.keys)
    offset = (args.account_offset if args.account_offset is not None else args.shard_index) % len(keys)
    client = OllamaCloudClient((keys[offset],), timeout_s=args.timeout)
    think_option: str | bool = False if args.think == "none" else args.think
    prompt_digest = hashlib.sha256(inspect.getsource(annotation_prompt).encode()).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as stream:
        for index, item in enumerate(rows, 1):
            if item["id"] in completed:
                continue
            record = {"id": item["id"], "model": args.model, "think": args.think, "prompt_sha256": prompt_digest}
            started = time.monotonic()
            try:
                response = client.chat(
                    args.model,
                    [{"role": "user", "content": annotation_prompt(item)}],
                    format_schema=ANNOTATION_SCHEMA,
                    options={"temperature": 0.0, "num_predict": 1024},
                    think=think_option,
                )
                raw_content = response.get("message", {}).get("content", "")
                record["raw_content"] = raw_content
                proposal, normalizations = parse_proposal(raw_content)
                # Reuse the strict taxonomy validator before accepting a proposal.
                from targetcheck.error_taxonomy import NaturalErrorAnnotation
                NaturalErrorAnnotation.from_dict({"id": item["id"], **proposal})
                record.update(status="ok", proposal=proposal, normalizations=normalizations)
                for field in ("prompt_eval_count", "eval_count", "total_duration"):
                    if field in response:
                        record[field] = response[field]
            except Exception as exc:
                record.update(status="error", error=f"{type(exc).__name__}: {str(exc)[:600]}")
            record["wall_seconds"] = round(time.monotonic() - started, 2)
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            print(f"[{index}/{len(rows)}] {item['id']} {record['status']}", flush=True)


if __name__ == "__main__":
    main()
