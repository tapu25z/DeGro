#!/bin/zsh
set -u

dataset="data/paired/mira_confirmatory_remaining_120.jsonl"
methods=(self_review grounded_self_review nonunique nonunique_grounding)
models=(gpt-oss:20b gemma4:31b)
mkdir -p results/raw

run_model() {
  local model="$1"
  local stem shard group worker offset output log_file pid result_code
  stem="${model//[:]/_}_mira_confirmatory_remaining_120"
  worker=0
  pids=()
  for shard in 0 1 2 3; do
    for group in 0 1; do
      if (( group == 0 )); then
        group_methods=(self_review grounded_self_review)
      else
        group_methods=(nonunique nonunique_grounding)
      fi
      offset=$((worker * 2))
      output="results/raw/${stem}_s${shard}_g${group}.jsonl"
      log_file="results/raw/${stem}_s${shard}_g${group}.log"
      .venv/bin/python scripts/run_pilot.py \
        --data "$dataset" --keys api.txt --model "$model" \
        --num-shards 4 --shard-index "$shard" --account-offset "$offset" \
        --accounts-per-worker 2 --timeout 45 \
        --methods "${group_methods[@]}" --out "$output" \
        >> "$log_file" 2>&1 &
      pids+=("$!")
      worker=$((worker + 1))
    done
  done
  result_code=0
  for pid in "${pids[@]}"; do wait "$pid" || result_code=1; done
  .venv/bin/python scripts/finalize_pilot.py \
    --data "$dataset" --methods "${methods[@]}" \
    --input-glob "results/raw/${stem}_s*.jsonl" \
    --out "results/${stem}_complete.jsonl" || result_code=1
  if [[ -f "results/${stem}_complete.jsonl" ]]; then
    .venv/bin/python scripts/analyze_pilot.py "results/${stem}_complete.jsonl" > "results/${stem}_summary.tsv"
    .venv/bin/python scripts/analyze_confirmatory.py "results/${stem}_complete.jsonl" > "results/${stem}_analysis.json"
  fi
  return "$result_code"
}

for model in "${models[@]}"; do
  print "[$model] confirmatory run started"
  run_model "$model" || true
  print "[$model] confirmatory run finalized"
done
