#!/bin/zsh
set -u

project_dir="/Users/buihuynhtay/Documents/ChatGPT/target-check"
cd "$project_dir" || exit 1
mkdir -p results/raw
exec >> results/pilot_background.log 2>&1

run_wave() {
  local pids=()
  local shard half methods offset output checkpoint
  for shard in 0 1 2 3; do
    checkpoint="results/raw/gpt_oss_20b_pilot_shard${shard}.jsonl"
    for half in 0 1; do
      if [[ "$half" == "0" ]]; then
        methods=(self_review nonunique nonunique_grounding random_pair)
      else
        methods=(target_witness minimal_witness targetcheck)
      fi
      # run_pilot.py applies modulo by the actual key count. Distinct offsets
      # spread the eight workers across up to eight configured accounts.
      offset=$(( shard * 2 + half ))
      output="results/raw/gpt_oss_20b_s${shard}_${half}.jsonl"
      .venv/bin/python scripts/run_pilot.py \
        --num-shards 4 --shard-index "$shard" --account-offset "$offset" \
        --methods "${methods[@]}" --out "$output" --resume-from "$checkpoint" \
        >> "results/raw/worker_${shard}_${half}.log" 2>&1 &
      pids+=("$!")
    done
  done
  local result_code=0 pid
  for pid in "${pids[@]}"; do
    wait "$pid" || result_code=1
  done
  return "$result_code"
}

echo "$(date -Iseconds) background pilot started"
run_wave
echo "$(date -Iseconds) retry wave started"
run_wave
echo "$(date -Iseconds) finalizing"
.venv/bin/python scripts/finalize_pilot.py
.venv/bin/python scripts/analyze_pilot.py results/gpt_oss_20b_pilot_complete.jsonl > results/gpt_oss_20b_pilot_summary.tsv
echo "$(date -Iseconds) background pilot complete"
