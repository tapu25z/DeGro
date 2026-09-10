#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p results/raw logs/math500_six_methods

model="${MODEL:-gpt-oss:20b}"
think="${THINK:-low}"
shards="${SHARDS:-17}"
slug="${model//[:\/.]/_}"
stem="${slug}_math500_six_methods_${think}_full_v2"

run_wave() {
  local wave="$1"
  local -a pids
  for ((i=0; i<shards; i++)); do
    .venv/bin/python scripts/run_math500_six_methods.py \
      --data data/math500/test.jsonl --keys api.txt \
      --model "$model" --think "$think" \
      --out "results/raw/${stem}_shard${i}.jsonl" \
      --num-shards "$shards" --shard-index "$i" \
      --account-offset "$i" --accounts-per-worker 1 \
      >"logs/math500_six_methods/${stem}_wave${wave}_shard${i}.log" 2>&1 &
    pids[$i]=$!
  done
  local status=0
  for pid in "${pids[@]}"; do
    wait "$pid" || status=1
  done
  return "$status"
}

echo "MATH-500 full | model=$model | think=$think | methods=6 | shards=$shards"
run_wave 1 || true
echo "Retrying only failed/missing method records"
run_wave 2 || true

.venv/bin/python scripts/analyze_math500_six_methods.py \
  "results/raw/${stem}_shard*.jsonl" \
  --json-out "results/${stem}_analysis.json" \
  --tsv-out "results/${stem}_summary.tsv"

echo "Summary: results/${stem}_summary.tsv"
echo "Analysis: results/${stem}_analysis.json"
echo "Logs: logs/math500_six_methods/${stem}_wave*_shard*.log"
