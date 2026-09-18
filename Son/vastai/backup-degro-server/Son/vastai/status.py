#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a DeGro JSONL run.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    rows = []
    malformed = 0
    if not args.path.exists():
        raise SystemExit(f"not found: {args.path}")
    for line in args.path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
    correct = sum(bool(row.get("correct")) for row in rows)
    print(f"records:   {len(rows)}")
    print(f"malformed: {malformed}")
    print(f"correct:   {correct}/{len(rows)} ({correct / len(rows):.1%})" if rows else "correct:   0/0")
    print(f"datasets:  {dict(Counter(row.get('dataset') for row in rows))}")
    print(f"decisions: {dict(Counter(row.get('decision') for row in rows))}")
    print(f"statuses:  {dict(Counter(row.get('run_status') for row in rows))}")


if __name__ == "__main__":
    main()
