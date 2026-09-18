"""Check whether requested thinking levels change deterministic Nano responses."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

from targetcheck.pilot import build_prompt, OUTPUT_SCHEMA, parse_decision, score, prompt_hash
from targetcheck.providers import OllamaCloudClient, load_api_keys


def main():
    out = Path("results/nano_think_levels_probe.jsonl")
    if out.exists():
        raise SystemExit(f"Refusing to overwrite {out}")
    rows = []
    for name in ("mira_pilot_80", "mira_heldout_100", "mira_confirmatory_remaining_120"):
        rows.extend(json.loads(line) for line in Path(f"data/paired/{name}.jsonl").read_text().splitlines())
    ids = {"ran-000585", "ran-000571", "ran-000594", "crt-000062"}
    selected = [r for r in rows if r["pair_id"] in ids]
    keys = load_api_keys("api.txt")
    tasks = [(row, level) for row in selected for level in ("low", "medium", "high")]

    def request(task):
        row, level = task
        started = time.monotonic()
        record = {"pair_id": row["pair_id"], "label": row["label"], "family": row["family"],
                  "method": "nonunique_grounding", "model": "nemotron-3-nano:30b",
                  "think": level, "temperature": 0, "seed": 42, "prompt_hash": prompt_hash()}
        client = OllamaCloudClient(keys, timeout_s=120)
        try:
            response = client.chat(record["model"], [{"role": "user", "content": build_prompt(record["method"], row)}],
                                   format_schema=OUTPUT_SCHEMA, options={"temperature": 0, "seed": 42}, think=level)
            message = response.get("message", {})
            record.update(status="ok", output=parse_decision(message.get("content", "")),
                          response=message, eval_count=response.get("eval_count"),
                          thinking_sha256=hashlib.sha256(message.get("thinking", "").encode()).hexdigest())
        except Exception as exc:
            record.update(status="error", error=str(exc)[:500])
        record["wall_seconds"] = round(time.monotonic() - started, 3)
        return row, record

    out.parent.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool, out.open("x") as stream:
        for row, record in pool.map(request, tasks):
            if record["status"] == "ok":
                record["score"] = score(row, record["output"])
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(record["pair_id"], record["label"], record["think"], record["status"], record.get("eval_count"), flush=True)


if __name__ == "__main__":
    main()
