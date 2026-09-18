#!/bin/zsh
set -euo pipefail

cd "${0:A:h:h}"
export PYTHONPATH=.
model='nemotron-3-super'
num_shards=${NUM_SHARDS:-8}
methods=(self_review grounded_self_review nonunique nonunique_grounding)
splits=(confirmatory120 pilot80 heldout100)
datasets=(data/paired/mira_confirmatory_remaining_120.jsonl data/paired/mira_pilot_80.jsonl data/paired/mira_heldout_100.jsonl)
stems=(nemotron_3_super_mira_confirmatory_remaining_120 nemotron_3_super_mira_pilot80_current_four_methods nemotron_3_super_mira_four_methods)
mkdir -p results/raw

run_split() {
  local split=$1
  local dataset stem output log worker shard method wave pid checkpoint
  local -a pids

  dataset=${datasets[$split]}
  stem=${stems[$split]}
  checkpoint="results/raw/${stem}_resume.jsonl"
  .venv/bin/python - "$stem" "$checkpoint" <<'PYCODE'
import glob, json, sys
from pathlib import Path
records = {}
for filename in sorted(glob.glob(f"results/raw/{sys.argv[1]}_s*.jsonl")):
    for line in Path(filename).read_text().splitlines():
        row = json.loads(line)
        if row.get("status") == "ok":
            records.setdefault((row["pair_id"], row["label"], row["method"]), row)
Path(sys.argv[2]).write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records.values()))
PYCODE
  for wave in 1 2 3; do
    print "[$stem] wave $wave"
    pids=()
    worker=0
    for ((shard=0; shard<num_shards; shard++)); do
      for method in "${methods[@]}"; do
        output="results/raw/${stem}_s${num_shards}_${shard}_${method}.jsonl"
        log="results/raw/${stem}_s${num_shards}_${shard}_${method}.log"
        .venv/bin/python scripts/run_pilot.py \
          --data "$dataset" --keys api.txt --model "$model" \
          --methods "$method" --num-shards "$num_shards" --shard-index "$shard" \
          --account-offset "$worker" --accounts-per-worker 17 --timeout 90 \
          --resume-from "$checkpoint" --out "$output" >> "$log" 2>&1 &
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
}

split_pids=()
for ((split=1; split<=${#splits}; split++)); do
  run_split "$split" &
  split_pids+=("$!")
done
failed=0
for pid in "${split_pids[@]}"; do
  wait "$pid" || failed=1
done
(( failed == 0 ))
.venv/bin/python scripts/assemble_mira_full300.py --models nemotron_3_super
