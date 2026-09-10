#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"

key_file="${TARGETCHECK_KEYS_FILE:-$project_dir/api.txt}"
model="${TARGETCHECK_MODEL:-gpt-oss:20b}"
pair_count="${1:-1}"
method_count=7

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating .venv and installing TargetCheck..."
  python3 -m venv .venv
  .venv/bin/pip install -q -e '.[dev]'
fi

if [[ ! -f "$key_file" ]]; then
  echo "Missing API key file: $key_file" >&2
  echo "Put one Ollama Cloud account/key per line in api.txt." >&2
  exit 1
fi

key_count=$(awk 'NF && $1 !~ /^#/ {n++} END {print n+0}' "$key_file")
if (( key_count == 0 )); then
  echo "No API keys found in $key_file" >&2
  exit 1
fi

dataset="data/paired/mira_pilot_80.jsonl"
if [[ ! -f "$dataset" ]]; then
  echo "Building the frozen 80-pair MIRA-Math pilot dataset..."
  .venv/bin/python scripts/build_paired_mira.py
fi

run_id=$(date -u +%Y%m%dT%H%M%SZ)
output="results/raw/smoke_${run_id}.jsonl"
summary="results/smoke_${run_id}.tsv"
mkdir -p results/raw

echo "TargetCheck smoke test"
echo "  model: $model"
echo "  configured accounts: $key_count"
echo "  pairs: $pair_count ($((pair_count * 2 * method_count)) API calls)"
echo "  output: $output"

.venv/bin/python scripts/run_pilot.py \
  --data "$dataset" \
  --out "$output" \
  --keys "$key_file" \
  --model "$model" \
  --limit-pairs "$pair_count"

.venv/bin/python scripts/analyze_pilot.py "$output" | tee "$summary"

errors=$(jq -s '[.[] | select(.status != "ok")] | length' "$output")
echo "Smoke test complete. Provider/parse errors: $errors"
echo "Summary saved to: $summary"
