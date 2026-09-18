"""Run GPT-OSS 20B and 120B on the frozen Geometry60 MIRA extension."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess

from targetcheck.pilot import prompt_hash

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/paired/mira_geometry_60.jsonl"
RUN = ROOT / "results/mira_geometry60"
RAW = RUN / "raw"
METHODS = ("self_review", "grounded_self_review", "nonunique", "nonunique_grounding")
MODELS = {"gpt_oss_20b": "gpt-oss:20b", "gpt_oss_120b": "gpt-oss:120b"}
SHARDS = 8


def main():
    os.chdir(ROOT)
    RUN.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    rows = [json.loads(line) for line in DATA.read_text().splitlines()]
    assert len(rows) == 120 and len({r["pair_id"] for r in rows}) == 60
    manifest = {"models": MODELS, "temperature": 1.0, "think": "medium", "methods": METHODS,
                "pairs": 60, "expected_per_model": 480, "prompt_hash": prompt_hash(),
                "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
                "selection": "first valid response; never select by score", "max_retry_waves": 4}
    manifest_path = RUN / "run_manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == json.loads(json.dumps(manifest)), "run config changed"
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}

    def consolidate(stem, model):
        completed = {}
        for path in sorted(RAW.glob(f"{stem}_*.jsonl")):
            for line in path.read_text().splitlines():
                record = json.loads(line)
                if record["status"] == "ok":
                    assert record["model"] == model and record["think"] == "medium"
                    assert record["prompt_hash"] == manifest["prompt_hash"]
                    completed.setdefault((record["pair_id"], record["label"], record["method"]), record)
        checkpoint = RUN / f"{stem}_resume.jsonl"
        checkpoint.write_text("".join(json.dumps(record) + "\n" for record in completed.values()))
        return checkpoint, len(completed)

    def worker(task):
        stem, model, shard, method = task
        name = f"{stem}_s{shard}_{method}"
        cmd = [str(ROOT / ".venv/bin/python"), "scripts/run_pilot.py", "--data", str(DATA),
               "--model", model, "--think", "medium", "--methods", method,
               "--num-shards", str(SHARDS), "--shard-index", str(shard),
               "--account-offset", str(shard * 8 + METHODS.index(method) * 2 + (stem == "gpt_oss_120b")),
               "--accounts-per-worker", "17", "--timeout", "120",
               "--resume-from", str(RUN / f"{stem}_resume.jsonl"), "--out", str(RAW / f"{name}.jsonl")]
        with (RAW / f"{name}.log").open("a") as log:
            return subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT).returncode

    tasks = [(stem, model, shard, method) for stem, model in MODELS.items()
             for shard in range(SHARDS) for method in METHODS]
    for wave in range(1, 5):
        for stem, model in MODELS.items():
            _, count = consolidate(stem, model)
            print(f"{stem} wave {wave}: preserve {count}/480 valid records", flush=True)
        with ThreadPoolExecutor(max_workers=64) as pool:
            codes = list(pool.map(worker, tasks))
        complete = True
        for stem in MODELS:
            output = RUN / f"{stem}_mira_geometry60_complete.jsonl"
            result = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/finalize_pilot.py",
                                     "--data", str(DATA), "--methods", *METHODS,
                                     "--input-glob", str(RAW / f"{stem}_*.jsonl"), "--out", str(output)], env=env)
            complete &= result.returncode == 0
        print(f"wave {wave}: complete={complete}; worker failures={sum(code != 0 for code in codes)}", flush=True)
        if complete:
            for stem in MODELS:
                output = RUN / f"{stem}_mira_geometry60_complete.jsonl"
                with (RUN / f"{stem}_summary.tsv").open("w") as stream:
                    subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/analyze_pilot.py", str(output)], env=env, stdout=stream, check=True)
                with (RUN / f"{stem}_analysis.json").open("w") as stream:
                    subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/analyze_confirmatory.py", str(output)], env=env, stdout=stream, check=True)
            print("COMPLETE: both models have 480 valid records", flush=True)
            return
    raise SystemExit("incomplete after four bounded waves")


if __name__ == "__main__":
    main()
