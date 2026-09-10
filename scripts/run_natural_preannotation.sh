#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p results/raw logs/natural_error

model="${MODEL:-gpt-oss:20b}"
think="${THINK:-low}"
shards="${SHARDS:-18}"
slug="${model//[:\/.]/_}"
packet="${PACKET:-data/natural_errors/gpt_oss_20b_math500/adjudication_packet.jsonl}"
expected="${EXPECTED:-292}"
stem="${PREANNOTATION_STEM:-${slug}_natural_error_preannotation_${think}}"
review_out="${REVIEW_OUT:-data/natural_errors/gpt_oss_20b_math500/${slug}_ai_assisted_human_review.jsonl}"

run_wave() {
  local wave="$1"
  local -a pids
  for ((i=0; i<shards; i++)); do
    .venv/bin/python scripts/preannotate_natural_errors.py \
      --packet "$packet" --keys api.txt --model "$model" --think "$think" \
      --out "results/raw/${stem}_shard${i}.jsonl" \
      --num-shards "$shards" --shard-index "$i" --account-offset "$i" \
      >"logs/natural_error/${stem}_wave${wave}_shard${i}.log" 2>&1 &
    pids[$i]=$!
  done
  local status=0
  for pid in "${pids[@]}"; do
    wait "$pid" || status=1
  done
  return "$status"
}

run_wave 1 || true
run_wave 2 || true
.venv/bin/python scripts/prepare_natural_error_review.py \
  "results/raw/${stem}_shard*.jsonl" \
  --packet "$packet" \
  --out "$review_out" \
  --expected "$expected"
