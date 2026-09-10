#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p results logs

shards="${SHARDS:-10}"
think="${THINK:-low}"
limit="${LIMIT:-50}"
stamp="math500_level45_symcode_${think}_${limit}"
declare -a pids

for ((i=0; i<shards; i++)); do
  .venv/bin/python scripts/run_olympiadbench_symcode.py \
    --dataset math500 --data data/math500/test.jsonl --levels 4 5 \
    --skip-cot \
    --out "results/${stamp}_shard${i}.jsonl" \
    --limit "$limit" --think "$think" \
    --num-shards "$shards" --shard-index "$i" \
    --account-offset "$((i * 2))" --accounts-per-worker 2 \
    >"logs/${stamp}_shard${i}.log" 2>&1 &
  pids[$i]=$!
done

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done

.venv/bin/python scripts/analyze_olympiadbench_symcode.py \
  "results/${stamp}_shard*.jsonl" --out "results/${stamp}_analysis.json"
exit "$status"
