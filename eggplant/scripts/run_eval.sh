#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
VENV="$ROOT_DIR/.eggplant-venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  bash "$ROOT_DIR/scripts/setup.sh"
fi
cd "$REPO_ROOT"
PYTHON="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$VENV/bin/python"
fi
"$PYTHON" "$ROOT_DIR/scripts/run_eval.py" "$@"
