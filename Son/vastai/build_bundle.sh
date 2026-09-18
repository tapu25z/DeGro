#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST="$SCRIPT_DIR/dist"
ARCHIVE="$DIST/degro-vastai.tar.gz"

mkdir -p "$DIST"
tar \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  -czf "$ARCHIVE" \
  -C "$PROJECT_ROOT" \
  pyproject.toml \
  targetcheck \
  scripts \
  data \
  tests \
  Son/__init__.py \
  Son/run_symcode_parallel.py \
  Son/vastai/run_local.py \
  Son/vastai/setup.sh \
  Son/vastai/smoke_test.sh \
  Son/vastai/run_all.sh \
  Son/vastai/status.py \
  Son/vastai/test_local.py \
  Son/vastai/README.md

echo "Created $ARCHIVE"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$ARCHIVE"
else
  sha256sum "$ARCHIVE"
fi
