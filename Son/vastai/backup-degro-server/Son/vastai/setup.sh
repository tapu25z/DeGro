#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen3:8b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Project: $PROJECT_ROOT"
echo "Model:   $MODEL"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "ERROR: nvidia-smi is unavailable. Use a CUDA-enabled Vast.ai template." >&2
  exit 1
fi
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

if ! command -v curl >/dev/null 2>&1; then
  apt-get update
  apt-get install -y curl ca-certificates
fi

if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

if [[ -x /venv/main/bin/python ]]; then
  PYTHON_BIN=/venv/main/bin/python
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
  python3 -m venv "$PROJECT_ROOT/.venv"
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "$PYTHON_BIN" -e "$PROJECT_ROOT"
else
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -e "$PROJECT_ROOT"
fi

mkdir -p "$SCRIPT_DIR/logs" "$SCRIPT_DIR/results"

# Vast.ai's base image requires long-running services to be managed by
# Supervisor. Ollama stays on loopback and is not exposed through a public port.
cat >/opt/supervisor-scripts/ollama-degro.sh <<'EOF'
#!/bin/bash
utils=/opt/supervisor-scripts/utils
. "${utils}/logging.sh"
. "${utils}/environment.sh"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NUM_PARALLEL=1
pty /usr/local/bin/ollama serve 2>&1
EOF
chmod +x /opt/supervisor-scripts/ollama-degro.sh

cat >/etc/supervisor/conf.d/ollama-degro.conf <<'EOF'
[program:ollama-degro]
environment=PROC_NAME="%(program_name)s"
command=/opt/supervisor-scripts/ollama-degro.sh
autostart=true
autorestart=unexpected
startretries=5
stdout_logfile=/dev/stdout
redirect_stderr=true
stdout_logfile_maxbytes=0
EOF

supervisorctl reread
supervisorctl update
supervisorctl restart ollama-degro

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "ERROR: Ollama did not become ready. Run: supervisorctl status ollama-degro" >&2
  exit 1
fi

OLLAMA_HOST=http://127.0.0.1:11434 ollama pull "$MODEL"
echo
echo "Setup complete. Run:"
echo "  bash Son/vastai/smoke_test.sh $MODEL"
