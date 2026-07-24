#!/usr/bin/env bash
# Production smoke checks for CurAI.
#
# Required:
#   APP_URL=https://app.cura-i.com ./scripts/prod_smoke.sh
#
# Optional authenticated checks:
#   PROD_SMOKE_AUTH_TOKEN=... RUN_AUTHENTICATED=true ./scripts/prod_smoke.sh
#   PROD_SMOKE_AUTH_TOKEN=... RUN_AUTHENTICATED=true RUN_MUTATIONS=true ./scripts/prod_smoke.sh

set -euo pipefail

APP_URL="${APP_URL:-https://app.cura-i.com}"
APP_URL="${APP_URL%/}"
RUN_AUTHENTICATED="${RUN_AUTHENTICATED:-false}"
RUN_MUTATIONS="${RUN_MUTATIONS:-false}"
AUTH_TOKEN="${PROD_SMOKE_AUTH_TOKEN:-}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

request_code() {
  local output_file="$1"
  shift
  curl --silent --show-error --location --max-time 45 \
    --output "$output_file" --write-out '%{http_code}' "$@" || true
}

expect_code() {
  local actual="$1"
  local expected="$2"
  local label="$3"
  [[ "$actual" == "$expected" ]] || fail "$label returned HTTP $actual (expected $expected)"
  printf 'OK: %s returned %s\n' "$label" "$actual"
}

printf 'CurAI production smoke: %s\n' "$APP_URL"

ROOT_CODE="$(request_code "$TMP_DIR/root.html" "$APP_URL/")"
expect_code "$ROOT_CODE" "200" "app shell"
grep -qi '<title>CurAI</title>' "$TMP_DIR/root.html" || fail "app shell is missing CurAI title"

HEALTH_CODE="$(request_code "$TMP_DIR/health.json" "$APP_URL/health")"
READY_CODE="$(request_code "$TMP_DIR/ready.json" "$APP_URL/ready")"
AUTH_CONFIG_CODE="$(request_code "$TMP_DIR/auth-config.json" "$APP_URL/auth/config")"
expect_code "$HEALTH_CODE" "200" "/health"
expect_code "$READY_CODE" "200" "/ready"
expect_code "$AUTH_CONFIG_CODE" "200" "/auth/config"

python3 - "$TMP_DIR/health.json" "$TMP_DIR/auth-config.json" <<'PY'
import json
import sys

health = json.load(open(sys.argv[1], encoding="utf-8"))
auth = json.load(open(sys.argv[2], encoding="utf-8"))
if health.get("status") != "ok":
    raise SystemExit("FAIL: /health payload does not report status=ok")
required = {"auth_disabled", "google_auth_enabled", "signup_mode"}
missing = sorted(required - auth.keys())
if missing:
    raise SystemExit(f"FAIL: /auth/config missing keys: {', '.join(missing)}")
print("OK: health and auth-config payloads are valid")
PY

if [[ "$RUN_AUTHENTICATED" != "true" ]]; then
  printf 'SKIP: authenticated checks disabled\n'
  printf 'Production smoke passed\n'
  exit 0
fi

[[ -n "$AUTH_TOKEN" ]] || fail "RUN_AUTHENTICATED=true but PROD_SMOKE_AUTH_TOKEN is empty"
AUTH_HEADER="Authorization: Bearer $AUTH_TOKEN"
ME_CODE="$(request_code "$TMP_DIR/me.json" -H "$AUTH_HEADER" "$APP_URL/auth/me")"
expect_code "$ME_CODE" "200" "/auth/me"
python3 - "$TMP_DIR/me.json" <<'PY'
import json
import sys

user = json.load(open(sys.argv[1], encoding="utf-8"))
if not user.get("id"):
    raise SystemExit("FAIL: /auth/me payload is missing user id")
print("OK: authenticated session is valid")
PY

if [[ "$RUN_MUTATIONS" != "true" ]]; then
  printf 'SKIP: chat/upload mutation checks disabled\n'
  printf 'Production smoke passed\n'
  exit 0
fi

CHAT_CODE="$(request_code "$TMP_DIR/chat.json" \
  -X POST \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  --data '{"messages":[{"role":"user","content":"Reply with exactly: PROD_SMOKE_OK"}]}' \
  "$APP_URL/chat")"
expect_code "$CHAT_CODE" "200" "/chat"
python3 - "$TMP_DIR/chat.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
if not str(payload.get("message") or "").strip():
    raise SystemExit("FAIL: /chat returned an empty message")
print("OK: authenticated chat returned a message")
PY

INGEST_CODE="$(request_code "$TMP_DIR/ingest.json" \
  -X POST \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  --data '{"documents":[{"text":"CurAI production smoke document. Safe to replace.","metadata":{"path":"prod-smoke.txt","title":"Production smoke"}}]}' \
  "$APP_URL/ingest")"
expect_code "$INGEST_CODE" "200" "/ingest"
python3 - "$TMP_DIR/ingest.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload.get("count") is None and not payload.get("job_id"):
    raise SystemExit("FAIL: /ingest returned neither count nor job_id")
print("OK: authenticated ingest was accepted")
PY

printf 'Production smoke passed\n'
