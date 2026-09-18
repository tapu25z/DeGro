#!/bin/zsh
set -u

dataset="data/paired/mira_pilot_80.jsonl"
all_methods=(self_review grounded_self_review nonunique nonunique_grounding)
models=(gpt-oss:20b gemma4:31b)
mkdir -p results/raw

run_model() {
  local model="$1"
  local stem shard group worker offset output log_file pid result_code wave
  if [[ "$model" == "gpt-oss:20b" ]]; then
    stem="gpt_oss_20b_mira_pilot80_current_four_methods"
  else
    stem="gemma4_31b_mira_pilot80_current_four_methods"
  fi

  for wave in 1 2; do
    print "[$model] wave $wave"
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
    for pid in "${pids[@]}"; do wait "$pid" || true; done
  done

  result_code=0
  .venv/bin/python scripts/finalize_pilot.py \
    --data "$dataset" --methods "${all_methods[@]}" \
    --input-glob "results/raw/${stem}_s*.jsonl" \
    --out "results/${stem}_complete.jsonl" || result_code=1
  .venv/bin/python scripts/analyze_pilot.py "results/${stem}_complete.jsonl" > "results/${stem}_summary.tsv"
  .venv/bin/python scripts/analyze_confirmatory.py "results/${stem}_complete.jsonl" > "results/${stem}_analysis.json"
  return "$result_code"
}

for model in "${models[@]}"; do
  print "[$model] pilot80 completion started"
  run_model "$model" || true
  print "[$model] pilot80 completion finalized"
done
