#!/bin/zsh
set -euo pipefail

cd "${0:A:h:h}"
export PYTHONPATH=.

dataset='data/paired/draw_paired/draw_paired_provisional_300.jsonl'
num_shards=${NUM_SHARDS:-8}
methods=(self_review grounded_self_review nonunique nonunique_grounding)
models=('gpt-oss:20b' 'gpt-oss:120b' 'nemotron-3-nano:30b')
stems=(gpt_oss_20b_draw_paired_provisional300 gpt_oss_120b_draw_paired_provisional300 nemotron_3_nano_30b_draw_paired_provisional300)
mkdir -p results/raw results logs/draw_paired

.venv/bin/python - "$dataset" > results/draw_paired_provisional300_run_manifest.json <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from targetcheck.pilot import prompt_hash

path = Path(sys.argv[1])
print(json.dumps({
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "stage": "PROVISIONAL_AWAITING_HUMAN_REVIEW",
    "data": str(path),
    "data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "models": ["gpt-oss:20b", "gpt-oss:120b", "nemotron-3-nano:30b"],
    "methods": ["self_review", "grounded_self_review", "nonunique", "nonunique_grounding"],
    "temperature": 1.0,
    "think": "medium",
    "prompt_hash": prompt_hash(),
    "claim_scope": "exploratory/provisional until exact spans and deletions are human-approved",
}, indent=2))
PY

run_model() {
  local index=$1
  local model=${models[$index]}
  local stem=${stems[$index]}
  local checkpoint="results/raw/${stem}_resume.jsonl"
  local wave shard method worker output log pid
  local -a pids

  .venv/bin/python - "$stem" "$checkpoint" <<'PY'
import glob, json, sys
from pathlib import Path
records = {}
for filename in sorted(glob.glob(f"results/raw/{sys.argv[1]}_s*.jsonl")):
    for line in Path(filename).read_text().splitlines():
        row = json.loads(line)
        if row.get("status") == "ok":
            records.setdefault((row["pair_id"], row["label"], row["method"]), row)
Path(sys.argv[2]).write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records.values()))
PY

  for wave in 1 2 3; do
    print "[$stem] wave $wave"
    pids=()
    worker=0
    for ((shard=0; shard<num_shards; shard++)); do
      for method in "${methods[@]}"; do
        output="results/raw/${stem}_s${num_shards}_${shard}_${method}.jsonl"
        log="logs/draw_paired/${stem}_s${num_shards}_${shard}_${method}.log"
        .venv/bin/python scripts/run_pilot.py \
          --data "$dataset" --keys api.txt --model "$model" \
          --methods "$method" --num-shards "$num_shards" --shard-index "$shard" \
          --account-offset "$worker" --accounts-per-worker 17 --timeout 120 \
          --resume-from "$checkpoint" --out "$output" >> "$log" 2>&1 &
        pids+=("$!")
        ((worker+=1))
      done
    done
    for pid in "${pids[@]}"; do wait "$pid" || true; done
  done

  .venv/bin/python scripts/finalize_pilot.py \
    --data "$dataset" --methods "${methods[@]}" \
    --input-glob "results/raw/${stem}_s*.jsonl" \
    --out "results/${stem}_complete.jsonl"
  .venv/bin/python scripts/analyze_pilot.py "results/${stem}_complete.jsonl" \
    > "results/${stem}_summary.tsv"
  .venv/bin/python scripts/analyze_confirmatory.py "results/${stem}_complete.jsonl" \
    > "results/${stem}_analysis.json"
  print "[$stem] complete"
}

model_pids=()
for ((index=1; index<=${#models}; index++)); do
  run_model "$index" > "logs/draw_paired/${stems[$index]}_run.log" 2>&1 &
  model_pids+=("$!")
done

failed=0
for pid in "${model_pids[@]}"; do
  wait "$pid" || failed=1
done
(( failed == 0 ))
