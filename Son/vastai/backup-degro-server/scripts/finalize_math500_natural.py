#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


DIRECT_FIELDS = ("direct_status", "direct_answer", "direct_correct", "direct_error")
SYMCODE_FIELDS = ("symcode_status", "symcode_raw", "symcode_value", "symcode_correct", "symcode_error")
STRUCTURED_FIELDS = (
    "status", "error_type", "error", "formalization_raw", "initial_verdict", "initial_value",
    "initial_correct", "review_output", "review_changed", "review_reason", "review_verdict",
    "review_value", "review_correct", "degro_output", "degro_changed", "degro_reason",
    "degro_verdict", "degro_value", "degro_correct",
)


def network_error(row: dict, prefix: str) -> bool:
    field = f"{prefix}_error" if prefix else "error"
    return "OllamaCloudError" in str(row.get(field, "")) or "all configured accounts failed" in str(row.get(field, ""))


def copy_fields(target: dict, source: dict, fields: tuple[str, ...]) -> None:
    for field in fields:
        target.pop(field, None)
        if field in source:
            target[field] = source[field]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for pattern in args.patterns:
        for filename in sorted(glob.glob(pattern)):
            rows.extend(map(json.loads, Path(filename).read_text().splitlines()))
    merged: dict[str, dict] = {}
    for row in rows:
        uid = row["unique_id"]
        if uid not in merged:
            merged[uid] = dict(row)
            continue
        current = merged[uid]
        if current.get("direct_status") == "error" and network_error(current, "direct") and row.get("direct_status") == "ok":
            copy_fields(current, row, DIRECT_FIELDS)
        if current.get("symcode_status") == "error" and network_error(current, "symcode") and row.get("symcode_status") in {"ok", "not_supported"}:
            copy_fields(current, row, SYMCODE_FIELDS)
        if current.get("status") == "error" and network_error(current, "") and row.get("status") != "error":
            copy_fields(current, row, STRUCTURED_FIELDS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in merged.values()))
    print(json.dumps({"records": len(merged)}))


if __name__ == "__main__":
    main()
