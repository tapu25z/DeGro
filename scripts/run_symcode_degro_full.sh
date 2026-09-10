#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data/math500 results/raw logs/symcode_degro

model="${MODEL:-gpt-oss:20b}"
think="${THINK:-low}"
shards="${SHARDS:-17}"
slug="${model//[:\/.]/_}"
source_stem="${SOURCE_STEM:-gpt-oss_20b_math500_six_methods_low_full_v2}"
stem="${slug}_math500_symcode_plus_degro_${think}_full"
cohort="data/math500/${stem}.jsonl"

.venv/bin/python scripts/build_symcode_degro_cohort.py \
  "results/raw/${source_stem}_shard*.jsonl" \
  --mode all --expected-results 500 --out "$cohort"

run_wave() {
  local wave="$1"
  local -a pids
  for ((i=0; i<shards; i++)); do
    .venv/bin/python scripts/run_symcode_degro.py \
      --data "$cohort" --keys api.txt \
      --model "$model" --think "$think" \
      --out "results/raw/${stem}_shard${i}.jsonl" \
      --num-shards "$shards" --shard-index "$i" \
      --account-offset "$i" --accounts-per-worker 1 \
      >"logs/symcode_degro/${stem}_wave${wave}_shard${i}.log" 2>&1 &
    pids[$i]=$!
  done
  local status=0
  for pid in "${pids[@]}"; do
    wait "$pid" || status=1
  done
  return "$status"
}

echo "MATH-500 SymCode+ -> DeGro | model=$model | think=$think | shards=$shards"
run_wave 1 || true
echo "Retrying failed records"
run_wave 2 || true

.venv/bin/python scripts/analyze_symcode_degro.py \
  "results/raw/${stem}_shard*.jsonl" \
  --out "results/${stem}_analysis.json"

echo "Analysis: results/${stem}_analysis.json"
echo "Logs: logs/symcode_degro/${stem}_wave*_shard*.log"
