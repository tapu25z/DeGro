#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen3:8b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -x /venv/main/bin/python ]]; then
  PYTHON_BIN=/venv/main/bin/python
else
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
fi

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" Son/vastai/run_local.py \
  --model "$MODEL" \
  --datasets math500 \
  --limit 2 \
  --workers 1 \
  --num-ctx 8192 \
  --out Son/vastai/results/smoke.jsonl
