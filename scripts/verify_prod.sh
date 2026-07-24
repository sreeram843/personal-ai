#!/usr/bin/env bash
# Post-deploy smoke checks against a running CurAI deployment.
#
# Usage:
#   ./scripts/verify_prod.sh
#   APP_URL=https://app.cura-i.com ./scripts/verify_prod.sh
#
# Exits non-zero on failed health/HTTPS checks.

set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"
APP_URL="${APP_URL%/}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

printf 'Smoke checks for %s\n' "$APP_URL"

HEALTH_CODE=$(curl -s -o /tmp/curai-health.json -w '%{http_code}' "$APP_URL/health" || true)
READY_CODE=$(curl -s -o /tmp/curai-ready.json -w '%{http_code}' "$APP_URL/ready" || true)

[[ "$HEALTH_CODE" == "200" ]] || fail "/health returned HTTP $HEALTH_CODE"
[[ "$READY_CODE" == "200" ]] || fail "/ready returned HTTP $READY_CODE"
printf 'OK: /health and /ready returned 200\n'

if [[ "$APP_URL" == https://* ]]; then
  curl -fsS --max-time 20 "$APP_URL/health" >/dev/null || fail "HTTPS health fetch failed"
  printf 'OK: HTTPS reachable\n'
fi

chmod +x "$ROOT_DIR/scripts/verify_prod_auth.sh"
APP_URL="$APP_URL" "$ROOT_DIR/scripts/verify_prod_auth.sh"

printf 'Smoke checks passed\n'
