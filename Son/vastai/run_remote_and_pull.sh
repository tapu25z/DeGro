#!/usr/bin/env bash
set -euo pipefail

# Run this script on the Mac, not inside the Vast.ai instance.
# It backs up the remote project, starts the full run in remote tmux, waits,
# and downloads results/logs when the run finishes.

REMOTE_HOST="${VAST_HOST:-root@115.73.36.100}"
REMOTE_PORT="${VAST_PORT:-32086}"
MODEL="${1:-qwen2:7b-instruct-q8_0}"
REMOTE_ROOT="${VAST_PROJECT_ROOT:-/workspace/degro}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
SESSION="degro-full-${STAMP}"
REMOTE_MARKER="${REMOTE_ROOT}/Son/vastai/.${SESSION}.done"
LOCAL_RUN_DIR="${SCRIPT_DIR}/remote_runs/${STAMP}"

SSH_OPTS=(-p "$REMOTE_PORT" -o ServerAliveInterval=30 -o ServerAliveCountMax=3)
SCP_OPTS=(-P "$REMOTE_PORT" -o ServerAliveInterval=30 -o ServerAliveCountMax=3)

mkdir -p "$LOCAL_RUN_DIR"

echo "[1/4] Backing up remote code to:"
echo "      $LOCAL_RUN_DIR/server-before-run"
scp "${SCP_OPTS[@]}" -r \
  "${REMOTE_HOST}:${REMOTE_ROOT}" \
  "$LOCAL_RUN_DIR/server-before-run"

echo "[2/4] Starting full run in remote tmux: $SESSION"
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" \
  "tmux new-session -d -s '$SESSION' 'cd $REMOTE_ROOT && bash Son/vastai/run_all.sh $MODEL; rc=\$?; printf \"%s\\n\" \"\$rc\" > $REMOTE_MARKER'"

echo "[3/4] Waiting for the remote run to finish..."
while true; do
  status="$(ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" \
    "if test -f '$REMOTE_MARKER'; then cat '$REMOTE_MARKER'; else printf WAIT; fi" \
    2>/dev/null || true)"

  if [[ "$status" =~ ^[0-9]+$ ]]; then
    break
  fi

  sleep 30
done

echo "[4/4] Run finished with exit code $status. Downloading results and logs..."
mkdir -p "$LOCAL_RUN_DIR/downloaded"

until scp "${SCP_OPTS[@]}" -r \
  "${REMOTE_HOST}:${REMOTE_ROOT}/Son/vastai/results" \
  "${REMOTE_HOST}:${REMOTE_ROOT}/Son/vastai/logs" \
  "$LOCAL_RUN_DIR/downloaded/"; do
  echo "Download failed; retrying in 30 seconds..."
  sleep 30
done

echo "Finished. Local files:"
echo "$LOCAL_RUN_DIR"

exit "$status"
