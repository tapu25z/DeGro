#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="+")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    by_id = {}
    for pattern in args.patterns:
        for filename in glob.glob(pattern):
            for line in Path(filename).read_text().splitlines():
                row = json.loads(line)
                by_id.setdefault(row["id"], row)
    rows = list(by_id.values())
    rate = lambda field: sum(bool(row.get(field)) for row in rows) / len(rows) if rows else 0.0
    report = {
        "records": len(rows),
        "subfields": dict(Counter(row["subfield"] for row in rows)),
        "cot_accuracy": rate("cot_correct"),
        "symcode_accuracy": rate("symcode_correct"),
        "symcode_plus_accuracy": rate("symcode_plus_correct"),
        "symcode_execution_rate": sum(row.get("symcode_status") == "ok" for row in rows) / len(rows) if rows else 0.0,
        "symcode_plus_execution_rate": sum(row.get("symcode_plus_status") == "ok" for row in rows) / len(rows) if rows else 0.0,
        "debug_activated": sum(bool(row.get("debug_activated")) for row in rows),
        "symcode_vs_cot": {
            "symcode_only": sum(row.get("symcode_correct") and not row.get("cot_correct") for row in rows),
            "cot_only": sum(row.get("cot_correct") and not row.get("symcode_correct") for row in rows),
        },
        "symcode_plus_vs_cot": {
            "symcode_plus_only": sum(row.get("symcode_plus_correct") and not row.get("cot_correct") for row in rows),
            "cot_only": sum(row.get("cot_correct") and not row.get("symcode_plus_correct") for row in rows),
        },
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
