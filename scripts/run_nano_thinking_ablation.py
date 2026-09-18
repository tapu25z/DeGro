"""Run a separate, resumable boolean-thinking ablation on frozen MIRA-300."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor
import sys
import argparse

from targetcheck.pilot import prompt_hash

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/nano_thinking_ablation"
METHODS = ("self_review", "grounded_self_review", "nonunique", "nonunique_grounding")
SHARDS = 8


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-shards", type=int, default=8)
    parser.add_argument("--start-wave", type=int, choices=(1, 2, 3, 4), default=1)
    args = parser.parse_args()
    assert args.num_shards > 0
    shards = args.num_shards
    os.chdir(ROOT)
    RUN.mkdir(exist_ok=True)
    raw = RUN / "raw"
    raw.mkdir(exist_ok=True)
    sources = [ROOT / f"data/paired/{name}.jsonl" for name in
               ("mira_pilot_80", "mira_heldout_100", "mira_confirmatory_remaining_120")]
    text = "".join(p.read_text().rstrip() + "\n" for p in sources)
    cases = [json.loads(line) for line in text.splitlines()]
    assert len(cases) == 600 and len({r["pair_id"] for r in cases}) == 300
    assert len({(r["pair_id"], r["label"]) for r in cases}) == 600
    data = RUN / "mira300_frozen.jsonl"
    manifest = {"model": "nemotron-3-nano:30b", "temperature": 1.0,
                "think_modes": [True, False], "methods": METHODS, "pairs": 300,
                "expected_per_mode": 2400, "prompt_hash": prompt_hash(),
                "data_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "sources": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                "max_retry_waves": 4, "selection": "first valid response; never select by score"}
    if data.exists():
        assert data.read_text() == text, "Frozen data changed; refusing resume"
        assert json.loads((RUN / "manifest.json").read_text()) == json.loads(json.dumps(manifest)), "Run config changed"
    else:
        data.write_text(text)
        (RUN / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}

    def worker(task):
        mode, shard, method = task
        name = f"{mode}_n{shards}_s{shard}_{method}"
        args = [str(ROOT / ".venv/bin/python"), "scripts/run_pilot.py", "--data", str(data),
                "--model", manifest["model"], "--think", "true" if mode == "on" else "false",
                "--methods", method, "--num-shards", str(shards), "--shard-index", str(shard),
                "--account-offset", str(shard * 8 + METHODS.index(method) * 2 + (mode == "off")),
                "--accounts-per-worker", "17", "--timeout", "120", "--out", str(raw / f"{name}.jsonl"),
                "--resume-from", str(RUN / f"{mode}_resume.jsonl")]
        with (raw / f"{name}.log").open("a") as log:
            return subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT).returncode

    tasks = [(mode, shard, method) for shard in range(shards) for method in METHODS for mode in ("on", "off")]
    for wave in range(args.start_wave, 5):
        for mode in ("on", "off"):
            completed = {}
            for path in sorted(raw.glob(f"{mode}_*.jsonl")):
                for line in path.read_text().splitlines():
                    record = json.loads(line)
                    if record["status"] == "ok":
                        assert record["think"] is (mode == "on") and record["prompt_hash"] == manifest["prompt_hash"]
                        completed.setdefault((record["pair_id"], record["label"], record["method"]), record)
            (RUN / f"{mode}_resume.jsonl").write_text("".join(json.dumps(record) + "\n" for record in completed.values()))
            print(f"{mode}: preserve {len(completed)} valid responses; schedule missing cases only", flush=True)
        print(f"wave {wave}: {len(tasks)} workers", flush=True)
        with ThreadPoolExecutor(max_workers=64) as pool:
            codes = list(pool.map(worker, tasks))
        complete = True
        for mode in ("on", "off"):
            output = RUN / f"nano_thinking_{mode}_complete.jsonl"
            result = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/finalize_pilot.py",
                                     "--data", str(data), "--methods", *METHODS,
                                     "--input-glob", str(raw / f"{mode}_*.jsonl"), "--out", str(output)], env=env)
            complete &= result.returncode == 0
        print(f"wave {wave}: complete={complete}; worker failures={sum(c != 0 for c in codes)}", flush=True)
        if complete:
            for mode in ("on", "off"):
                output = RUN / f"nano_thinking_{mode}_complete.jsonl"
                rows = [json.loads(line) for line in output.read_text().splitlines()]
                assert all(r["think"] is (mode == "on") and r["prompt_hash"] == manifest["prompt_hash"] for r in rows)
                for analyzer, suffix in (("analyze_pilot.py", "summary.tsv"), ("analyze_confirmatory.py", "analysis.json")):
                    with (RUN / f"nano_thinking_{mode}_{suffix}").open("w") as stream:
                        subprocess.run([str(ROOT / ".venv/bin/python"), f"scripts/{analyzer}", str(output)],
                                       env=env, stdout=stream, check=True)
            print("COMPLETE: both modes have 2400 valid records", flush=True)
            return
    raise SystemExit("Incomplete after four bounded waves; inspect raw errors before further retries")


if __name__ == "__main__":
    main()
