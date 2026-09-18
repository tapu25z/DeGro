#!/bin/zsh
set -u

project_dir="${0:A:h:h}"
cd "$project_dir" || exit 1
mkdir -p results/raw
exec >> results/heldout_background.log 2>&1

dataset="data/paired/mira_heldout_100.jsonl"
result_stem="gpt_oss_20b_confirmatory_100"
methods_all=(self_review nonunique nonunique_grounding target_witness minimal_witness targetcheck)

run_wave() {
  local pids=()
  local shard half methods offset output
  for shard in 0 1 2 3; do
    for half in 0 1; do
      if [[ "$half" == "0" ]]; then
        methods=(self_review nonunique nonunique_grounding)
      else
        methods=(target_witness minimal_witness targetcheck)
      fi
      if [[ "$shard" == "1" ]]; then
        offset=$(( 8 + half ))
      else
        offset=$(( shard * 2 + half ))
      fi
      output="results/raw/${result_stem}_s${shard}_${half}.jsonl"
      .venv/bin/python scripts/run_pilot.py \
        --data "$dataset" --num-shards 4 --shard-index "$shard" \
        --account-offset "$offset" --methods "${methods[@]}" --out "$output" \
        >> "results/raw/${result_stem}_worker_${shard}_${half}.log" 2>&1 &
      pids+=("$!")
    done
  done
  local result_code=0 pid
  for pid in "${pids[@]}"; do
    wait "$pid" || result_code=1
  done
  return "$result_code"
}

echo "$(date -Iseconds) held-out run started"
run_wave
echo "$(date -Iseconds) held-out retry wave started"
run_wave
echo "$(date -Iseconds) held-out finalizing"
.venv/bin/python scripts/finalize_pilot.py \
  --data "$dataset" \
  --out "results/${result_stem}_complete.jsonl" \
  --input-glob "results/raw/${result_stem}_s*.jsonl" \
  --methods "${methods_all[@]}"
.venv/bin/python scripts/analyze_pilot.py \
  "results/${result_stem}_complete.jsonl" > "results/${result_stem}_summary.tsv"
echo "$(date -Iseconds) held-out run complete"
