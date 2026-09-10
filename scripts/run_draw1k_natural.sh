#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p results/raw logs/draw1k_natural

model="${MODEL:-gpt-oss:20b}"
think="${THINK:-low}"
shards="${SHARDS:-18}"
slug="${model//[:\/.]/_}"
stem="${slug}_draw1k_natural_test_${think}"

run_wave() {
  local wave="$1"
  local -a pids
  for ((i=0; i<shards; i++)); do
    .venv/bin/python scripts/run_draw1k_natural.py \
      --data data/draw1k/draw1k.jsonl --keys api.txt --model "$model" --think "$think" \
      --split test --out "results/raw/${stem}_shard${i}.jsonl" \
      --num-shards "$shards" --shard-index "$i" --account-offset "$i" \
      >"logs/draw1k_natural/${stem}_wave${wave}_shard${i}.log" 2>&1 &
    pids[$i]=$!
  done
  local status=0
  for pid in "${pids[@]}"; do wait "$pid" || status=1; done
  return "$status"
}

run_wave 1 || true
run_wave 2 || true
.venv/bin/python scripts/analyze_draw1k_natural.py \
  "results/raw/${stem}_shard*.jsonl" --expected 200 \
  --out "results/${stem}_analysis.json"
.venv/bin/python scripts/build_draw1k_natural_study.py \
  "results/raw/${stem}_shard*.jsonl" \
  --data data/draw1k/draw1k.jsonl \
  --out-dir "data/natural_errors/${slug}_draw1k_test"
