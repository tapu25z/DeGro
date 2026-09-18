#!/bin/zsh
set -euo pipefail

cd "${0:A:h:h}"
export PYTHONPATH=.
model='gpt-oss:120b'
methods=(self_review grounded_self_review nonunique nonunique_grounding)
splits=(pilot80 heldout100 confirmatory120)
datasets=(data/paired/mira_pilot_80.jsonl data/paired/mira_heldout_100.jsonl data/paired/mira_confirmatory_remaining_120.jsonl)
stems=(gpt_oss_120b_mira_pilot80_current_four_methods gpt_oss_120b_mira_four_methods gpt_oss_120b_mira_confirmatory_remaining_120)
mkdir -p results/raw

for ((split=1; split<=${#splits}; split++)); do
  dataset=${datasets[$split]}
  stem=${stems[$split]}
  for wave in 1 2; do
    print "[$stem] wave $wave"
    pids=()
    worker=0
    for shard in 0 1 2 3; do
      for method in "${methods[@]}"; do
        output="results/raw/${stem}_s${shard}_${method}.jsonl"
        log="results/raw/${stem}_s${shard}_${method}.log"
        .venv/bin/python scripts/run_pilot.py \
          --data "$dataset" --keys api.txt --model "$model" \
          --methods "$method" --num-shards 4 --shard-index "$shard" \
          --account-offset "$worker" --accounts-per-worker 1 --timeout 90 \
          --out "$output" >> "$log" 2>&1 &
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
  .venv/bin/python scripts/analyze_pilot.py "results/${stem}_complete.jsonl" > "results/${stem}_summary.tsv"
  .venv/bin/python scripts/analyze_confirmatory.py "results/${stem}_complete.jsonl" > "results/${stem}_analysis.json"
  print "[$stem] complete"
done
