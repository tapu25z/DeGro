#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from targetcheck import ModelSpec, check_target_determinacy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    for line in args.path.read_text().splitlines():
        row = json.loads(line)
        result = check_target_determinacy(ModelSpec.from_dict(row["spec"]))
        print(json.dumps({"pair_id": row["pair_id"], "label": row["label"], **result.__dict__}, default=str))


if __name__ == "__main__":
    main()
