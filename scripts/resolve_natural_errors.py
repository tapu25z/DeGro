#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

try:
    from scripts.adjudicate_natural_errors import load
except ModuleNotFoundError:
    from adjudicate_natural_errors import load
from targetcheck.error_taxonomy import ErrorLabel, NaturalErrorAnnotation


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge agreements and third-pass resolutions into final labels.")
    parser.add_argument("annotation_a", type=Path)
    parser.add_argument("annotation_b", type=Path)
    parser.add_argument("--resolutions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    a, b = load(args.annotation_a), load(args.annotation_b)
    if set(a) != set(b):
        raise SystemExit("annotation ID mismatch")
    resolutions = {}
    for line_number, line in enumerate(args.resolutions.read_text().splitlines(), 1):
        raw = json.loads(line)
        uid = raw.get("id")
        if uid in resolutions:
            raise SystemExit(f"{args.resolutions}:{line_number}: duplicate id {uid}")
        if not isinstance(raw.get("resolution"), dict):
            raise SystemExit(f"{args.resolutions}:{line_number}: resolution must be a completed annotation object")
        resolution = dict(raw["resolution"])
        resolution["id"] = uid
        try:
            resolutions[uid] = NaturalErrorAnnotation.from_dict(resolution)
        except (ValueError, TypeError) as exc:
            raise SystemExit(f"{args.resolutions}:{line_number}: {exc}") from exc
    resolved = []
    needed = set()
    for uid in sorted(a):
        same = (a[uid].primary_label, a[uid].target_critical_underformalization) == (
            b[uid].primary_label, b[uid].target_critical_underformalization
        )
        if same:
            choice = a[uid]
        else:
            needed.add(uid)
            if uid not in resolutions:
                raise SystemExit(f"missing third-pass resolution for {uid}")
            choice = resolutions[uid]
        if choice.primary_label == ErrorLabel.UNSURE:
            raise SystemExit(f"unresolved UNSURE label for {uid}")
        resolved.append(asdict(choice))
    extras = set(resolutions) - needed
    if extras:
        raise SystemExit(f"resolutions supplied for non-disagreements: {sorted(extras)[:5]}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in resolved))
    print(json.dumps({"records": len(resolved), "third_pass_resolutions": len(needed)}))


if __name__ == "__main__":
    main()
