#!/usr/bin/env bash
# Create the isolated eggplant virtualenv and install eval dependencies.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/.eggplant-venv"

if [[ ! -d "$REPO_ROOT/.venv" ]]; then
  echo "Main project .venv not found at $REPO_ROOT/.venv — create it first (python -m venv .venv && pip install -r requirements.txt)."
  exit 1
fi

python3 -m venv "$VENV_DIR"
# Prefer the repo's main interpreter (3.12) — datasets/dill break on some 3.14 builds.
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  rm -rf "$VENV_DIR"
  "$REPO_ROOT/.venv/bin/python" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"

mkdir -p "$ROOT_DIR/datasets" "$ROOT_DIR/results"

echo ""
echo "Eggplant env ready: $VENV_DIR"
echo "  Download:  bash eggplant/scripts/download_datasets.sh"
echo "  Evaluate:  bash eggplant/scripts/run_eval.sh"
