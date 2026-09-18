#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path


DATASET = "HuggingFaceH4/MATH-500"
API = "https://datasets-server.huggingface.co/rows"


def main() -> None:
    output = Path("data/math500/test.jsonl")
    rows: list[dict] = []
    for offset in range(0, 500, 100):
        query = urllib.parse.urlencode(
            {"dataset": DATASET, "config": "default", "split": "test", "offset": offset, "length": 100}
        )
        with urllib.request.urlopen(f"{API}?{query}", timeout=60) as response:
            payload = json.load(response)
        rows.extend(item["row"] for item in payload["rows"])
    output.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    output.write_text(content, encoding="utf-8")
    manifest = {
        "dataset": DATASET,
        "split": "test",
        "rows": len(rows),
        "source_api": API,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
