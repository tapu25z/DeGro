#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"

dataset="data/paired/mira_heldout_100.jsonl"
keys_file="api.txt"
num_shards=4
limit_pairs=""
reuse_gpt=1
dry_run=0

usage() {
  print "Usage: $0 [options]"
  print ""
  print "Run the four-method MIRA-Math ablation on gpt-oss:20b and gemma4:31b."
  print ""
  print "Options:"
  print "  --data PATH          Paired MIRA JSONL (default: $dataset)"
  print "  --keys PATH          Ollama Cloud key file (default: $keys_file)"
  print "  --shards N           Parallel data shards per model (default: $num_shards)"
  print "  --limit-pairs N      Run only the first N pairs (smoke testing)"
  print "  --no-reuse-gpt       Re-run GPT-OSS instead of reusing existing results"
  print "  --dry-run            Print the run configuration without API calls"
  print "  -h, --help           Show this help"
}

while (( $# > 0 )); do
  case "$1" in
    --data)
      dataset="$2"
      shift 2
      ;;
    --keys)
      keys_file="$2"
      shift 2
      ;;
    --shards)
      num_shards="$2"
      shift 2
      ;;
    --limit-pairs)
      limit_pairs="$2"
      shift 2
      ;;
    --no-reuse-gpt)
      reuse_gpt=0
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      print -u2 "Unknown option: $1"
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$dataset" ]]; then
  print -u2 "Dataset not found: $dataset"
  exit 1
fi
if [[ ! "$num_shards" =~ '^[1-9][0-9]*$' ]]; then
  print -u2 "--shards must be a positive integer"
  exit 2
fi
if [[ -n "$limit_pairs" && ! "$limit_pairs" =~ '^[1-9][0-9]*$' ]]; then
  print -u2 "--limit-pairs must be a positive integer"
  exit 2
fi

models=("gpt-oss:20b" "gemma4:31b")
methods_all=(self_review grounded_self_review nonunique nonunique_grounding)
default_dataset="data/paired/mira_heldout_100.jsonl"

print "Dataset: $dataset"
print "Models: ${models[*]}"
print "Methods: ${methods_all[*]}"
print "Shards per model: $num_shards"
[[ -n "$limit_pairs" ]] && print "Pair limit: $limit_pairs"

if (( dry_run )); then
  print "Dry run complete; no API calls were made."
  exit 0
fi
if [[ ! -f "$keys_file" ]]; then
  print -u2 "API key file not found: $keys_file"
  exit 1
fi

mkdir -p results/raw

run_model() {
  local model="$1"
  local model_slug="${model//[^A-Za-z0-9]/_}"
  local stem="${model_slug}_mira_four_methods"
  local complete_path="results/${stem}_complete.jsonl"
  local summary_path="results/${stem}_summary.tsv"
  local analysis_path="results/${stem}_analysis.json"
  local run_log="results/${stem}.log"
  local -a resume_args finalize_args limit_args

  resume_args=()
  finalize_args=(--input-glob "results/raw/${stem}_s*.jsonl")
  limit_args=()
  if [[ -n "$limit_pairs" ]]; then
    limit_args=(--limit-pairs "$limit_pairs")
  fi

  # The repository already contains all four GPT-OSS methods for the default
  # 100-pair set, split across these two completed result files. Reuse them by
  # default to avoid 800 duplicate paid requests.
  if [[ "$model" == "gpt-oss:20b" && "$dataset" == "$default_dataset" \
        && -z "$limit_pairs" && "$reuse_gpt" == "1" ]]; then
    local primary="results/gpt_oss_20b_confirmatory_100_complete.jsonl"
    local decision="results/gpt_oss_20b_decision_baselines_100_complete.jsonl"
    if [[ -f "$primary" && -f "$decision" ]]; then
      resume_args=(--resume-from "$primary" "$decision")
      finalize_args+=(--input-glob "$primary" --input-glob "$decision")
      print "[$model] reusing completed GPT-OSS records where available"
    fi
  fi

  run_wave() {
    local -a pids methods
    local shard group worker output worker_log offset pid result_code
    pids=()
    worker=0
    for (( shard=0; shard<num_shards; shard++ )); do
      for group in 0 1; do
        if (( group == 0 )); then
          methods=(self_review grounded_self_review)
        else
          methods=(nonunique nonunique_grounding)
        fi
        offset=$((worker * 2))
        output="results/raw/${stem}_s${shard}_g${group}.jsonl"
        worker_log="results/raw/${stem}_s${shard}_g${group}.log"
        .venv/bin/python scripts/run_pilot.py \
          --data "$dataset" \
          --keys "$keys_file" \
          --model "$model" \
          --num-shards "$num_shards" \
          --shard-index "$shard" \
          --account-offset "$offset" \
          --methods "${methods[@]}" \
          --out "$output" \
          "${limit_args[@]}" \
          "${resume_args[@]}" \
          >> "$worker_log" 2>&1 &
        pids+=("$!")
        worker=$((worker + 1))
      done
    done

    result_code=0
    for pid in "${pids[@]}"; do
      wait "$pid" || result_code=1
    done
    return "$result_code"
  }

  print "[$model] first wave started" | tee -a "$run_log"
  run_wave || true
  print "[$model] retry wave started" | tee -a "$run_log"
  run_wave || true

  print "[$model] finalizing" | tee -a "$run_log"
  .venv/bin/python scripts/finalize_pilot.py \
    --data "$dataset" \
    --out "$complete_path" \
    --methods "${methods_all[@]}" \
    "${limit_args[@]}" \
    "${finalize_args[@]}"

  .venv/bin/python scripts/analyze_pilot.py "$complete_path" > "$summary_path"
  .venv/bin/python scripts/analyze_confirmatory.py "$complete_path" > "$analysis_path"
  print "[$model] complete: $summary_path" | tee -a "$run_log"
}

for model in "${models[@]}"; do
  run_model "$model"
done

print "All requested MIRA-Math runs are complete."
