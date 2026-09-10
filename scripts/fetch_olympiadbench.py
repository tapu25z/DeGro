#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq


URL = (
    "https://huggingface.co/datasets/Hothan/OlympiadBench/resolve/main/"
    "OlympiadBench/OE_TO_maths_en_COMP/OE_TO_maths_en_COMP.parquet"
)
OUT = Path("data/olympiadbench/oe_to_maths_en_comp.jsonl")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        urllib.request.urlretrieve(URL, tmp.name)
        rows = pq.read_table(tmp.name).to_pylist()
    payload = "".join(
        json.dumps(
            {
                "id": row["id"],
                "question": row["question"],
                "final_answer": row["final_answer"],
                "is_multiple_answer": row["is_multiple_answer"],
                "answer_type": row["answer_type"],
                "subfield": row["subfield"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    )
    OUT.write_text(payload)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    OUT.with_suffix(".manifest.json").write_text(
        json.dumps({"source": URL, "records": len(rows), "sha256": digest}, indent=2) + "\n"
    )
    print(json.dumps({"records": len(rows), "sha256": digest}))


if __name__ == "__main__":
    main()
