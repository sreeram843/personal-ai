#!/usr/bin/env bash
# Verify remote inference reachability (LM Studio + Ollama) before live eggplant tests.
#
# Usage:
#   ./scripts/check_remote_inference.sh
#   REMOTE_LM_HOST=192.168.8.245 ./scripts/check_remote_inference.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_LM_HOST="${REMOTE_LM_HOST:-192.168.8.245}"
OLLAMA_CHECK_URL="${OLLAMA_CHECK_URL:-http://127.0.0.1:11434}"

printf '\n=== Remote inference connectivity ===\n'
printf 'LM Studio host: %s:1234\n' "$REMOTE_LM_HOST"
printf 'Ollama check:   %s\n\n' "$OLLAMA_CHECK_URL"

curl -sS -m 8 -w "LM Studio /v1/models → HTTP %{http_code} (%{time_total}s)\n" \
  "http://${REMOTE_LM_HOST}:1234/v1/models" | head -5
echo

curl -sS -m 8 -w "Ollama /api/tags → HTTP %{http_code} (%{time_total}s)\n" \
  "${OLLAMA_CHECK_URL%/}/api/tags" | head -5
echo

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'personal-ai-app'; then
  printf 'From app container:\n'
  docker exec personal-ai-app curl -sS -m 8 -w "HTTP %{http_code}\n" \
    "http://${REMOTE_LM_HOST}:1234/v1/models" | head -3
else
  printf '~ personal-ai-app container not running (skip in-container check)\n'
fi

printf '\nOptional full eggplant connectivity report:\n'
printf '  cd %s && .venv/bin/python eggplant/scripts/run_eval.py --connectivity-check\n' "$ROOT_DIR"
