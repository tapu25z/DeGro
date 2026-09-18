"""Run Nano on the frozen, validated MIRA near-fragment extension."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import argparse

from targetcheck.pilot import prompt_hash

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/paired/mira_near_fragment_174.jsonl"
RUN = ROOT / "results/nano_mira_near_fragment_174"
RAW = RUN / "raw"
METHODS = ("self_review", "grounded_self_review", "nonunique", "nonunique_grounding")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-shards", type=int, default=8)
    parser.add_argument("--start-wave", type=int, choices=(1, 2, 3, 4), default=1)
    args = parser.parse_args()
    assert args.num_shards > 0
    shards = args.num_shards
    os.chdir(ROOT)
    RUN.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    rows = [json.loads(line) for line in DATA.read_text().splitlines()]
    assert len(rows) == 348 and len({r["pair_id"] for r in rows}) == 174
    manifest = {"model": "nemotron-3-nano:30b", "temperature": 1.0, "think": True,
                "methods": METHODS, "pairs": 174, "expected_records": 1392,
                "prompt_hash": prompt_hash(), "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
                "selection": "first valid response; never select by score", "max_retry_waves": 4}
    manifest_path = RUN / "run_manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == json.loads(json.dumps(manifest)), "run config changed"
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}

    def consolidate():
        completed = {}
        for path in sorted(RAW.glob("*.jsonl")):
            for line in path.read_text().splitlines():
                record = json.loads(line)
                if record["status"] == "ok":
                    assert record["think"] is True and record["prompt_hash"] == manifest["prompt_hash"]
                    completed.setdefault((record["pair_id"], record["label"], record["method"]), record)
        checkpoint = RUN / "resume.jsonl"
        checkpoint.write_text("".join(json.dumps(record) + "\n" for record in completed.values()))
        return checkpoint, len(completed)

    def worker(task):
        shard, method = task
        name = f"n{shards}_s{shard}_{method}"
        cmd = [str(ROOT / ".venv/bin/python"), "scripts/run_pilot.py", "--data", str(DATA),
               "--model", manifest["model"], "--think", "true", "--methods", method,
               "--num-shards", str(shards), "--shard-index", str(shard),
               "--account-offset", str(shard * 4 + METHODS.index(method)), "--accounts-per-worker", "17",
               "--timeout", "120", "--resume-from", str(RUN / "resume.jsonl"),
               "--out", str(RAW / f"{name}.jsonl")]
        with (RAW / f"{name}.log").open("a") as log:
            return subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT).returncode

    tasks = [(shard, method) for shard in range(shards) for method in METHODS]
    for wave in range(args.start_wave, 5):
        _, count = consolidate()
        print(f"wave {wave}: preserve {count}/1392 valid records", flush=True)
        with ThreadPoolExecutor(max_workers=32) as pool:
            codes = list(pool.map(worker, tasks))
        output = RUN / "nano_mira_near_fragment_174_complete.jsonl"
        result = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/finalize_pilot.py",
                                 "--data", str(DATA), "--methods", *METHODS,
                                 "--input-glob", str(RAW / "*.jsonl"), "--out", str(output)], env=env)
        if result.returncode == 0:
            with (RUN / "summary.tsv").open("w") as stream:
                subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/analyze_pilot.py", str(output)], env=env, stdout=stream, check=True)
            with (RUN / "analysis.json").open("w") as stream:
                subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/analyze_confirmatory.py", str(output)], env=env, stdout=stream, check=True)
            print("COMPLETE: 1392 valid records", flush=True)
            return
        print(f"wave {wave}: incomplete; worker failures={sum(code != 0 for code in codes)}", flush=True)
    raise SystemExit("incomplete after four bounded waves")


if __name__ == "__main__":
    main()
