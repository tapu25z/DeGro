#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data/olympiadbench results logs
if [[ ! -f data/olympiadbench/oe_to_maths_en_comp.jsonl ]]; then
  .venv/bin/python scripts/fetch_olympiadbench.py
fi

shards="${SHARDS:-10}"
think="${THINK:-high}"
limit="${LIMIT:-50}"
stamp="olympiadbench_symcode_${think}_${limit}"
declare -a pids

for ((i=0; i<shards; i++)); do
  .venv/bin/python scripts/run_olympiadbench_symcode.py \
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
