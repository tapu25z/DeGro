#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen3:8b}"
shift || true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$SCRIPT_DIR/logs/${MODEL//[:\/]/_}_$STAMP.log"

if [[ -x /venv/main/bin/python ]]; then
  PYTHON_BIN=/venv/main/bin/python
else
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
fi

mkdir -p "$SCRIPT_DIR/logs" "$SCRIPT_DIR/results"
cd "$PROJECT_ROOT"

set -o pipefail
"$PYTHON_BIN" Son/vastai/run_local.py \
  --model "$MODEL" \
  --workers 1 \
  --num-ctx 8192 \
  "$@" 2>&1 | tee -a "$LOG"
