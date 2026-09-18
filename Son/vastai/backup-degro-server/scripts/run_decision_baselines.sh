#!/bin/zsh
set -u

project_dir="${0:A:h:h}"
cd "$project_dir" || exit 1
mkdir -p results/raw

dataset="data/paired/mira_heldout_100.jsonl"
stem="gpt_oss_20b_decision_baselines_100"
methods=(grounded_self_review minimal_witness_grounding)

run_wave() {
  local pids=()
  local worker=0 shard method output log
  for shard in 0 1 2 3; do
    for method in "${methods[@]}"; do
      output="results/raw/${stem}_s${shard}_${method}.jsonl"
      log="results/raw/${stem}_worker_${shard}_${method}.log"
      .venv/bin/python scripts/run_pilot.py \
        --data "$dataset" --num-shards 4 --shard-index "$shard" \
        --account-offset "$((worker * 2))" --methods "$method" --out "$output" \
        >> "$log" 2>&1 &
      pids+=("$!")
      worker=$((worker + 1))
    done
  done
  local result_code=0 pid
  for pid in "${pids[@]}"; do
    wait "$pid" || result_code=1
  done
  return "$result_code"
}

run_wave
run_wave

.venv/bin/python scripts/finalize_pilot.py \
  --data "$dataset" \
  --out "results/${stem}_complete.jsonl" \
  --input-glob "results/raw/${stem}_s*.jsonl" \
  --methods "${methods[@]}"

.venv/bin/python scripts/analyze_pilot.py \
  "results/${stem}_complete.jsonl" > "results/${stem}_summary.tsv"

.venv/bin/python scripts/analyze_confirmatory.py \
  results/gpt_oss_20b_confirmatory_100_complete.jsonl \
  "results/${stem}_complete.jsonl" > results/gpt_oss_20b_decision_analysis.json
