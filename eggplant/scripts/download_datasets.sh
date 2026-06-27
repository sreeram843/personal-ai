#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/.eggplant-venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  bash "$ROOT_DIR/scripts/setup.sh"
fi
"$VENV/bin/python" "$ROOT_DIR/scripts/download_datasets.py" "$@"
