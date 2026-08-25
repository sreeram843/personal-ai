#!/usr/bin/env bash
# Deep production smoke for CurieAI — public health + authenticated workflow matrix.
#
# Requires a Bearer JWT (prod disables email token minting):
#   1. Sign in at https://app.cura-i.com
#   2. DevTools → Application → Local Storage → personal-ai-auth-token
#   3. Run:
#        export AUTH_TOKEN='…'
#        APP_URL=https://app.cura-i.com ./scripts/prod_deep_smoke.sh
#
# Also accepts PROD_SMOKE_AUTH_TOKEN as an alias for AUTH_TOKEN.
#
# Creates conversations / chat traffic under the token's user and consumes provider tokens.

set -euo pipefail

APP_URL="${APP_URL:-https://app.cura-i.com}"
APP_URL="${APP_URL%/}"
AUTH_TOKEN="${AUTH_TOKEN:-${PROD_SMOKE_AUTH_TOKEN:-}}"
PUBLIC_TIMEOUT="${PUBLIC_TIMEOUT:-45}"
CHAT_TIMEOUT="${CHAT_TIMEOUT:-180}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS=0
FAIL=0
WARN=0
RESULTS=()

pass() {
  printf 'OK: %s\n' "$1"
  PASS=$((PASS + 1))
  RESULTS+=("PASS|$1")
}

fail_soft() {
  printf 'FAIL: %s\n' "$1" >&2
  FAIL=$((FAIL + 1))
  RESULTS+=("FAIL|$1")
}

warn() {
  printf 'WARN: %s\n' "$1" >&2
  WARN=$((WARN + 1))
  RESULTS+=("WARN|$1")
}

fail_hard() {
  printf 'FAIL: %s\n' "$1" >&2
  FAIL=$((FAIL + 1))
  RESULTS+=("FAIL|$1")
  _print_summary
  exit 1
}

request_code() {
  local output_file="$1"
  local max_time="$2"
  shift 2
  curl --silent --show-error --location --max-time "$max_time" \
    --output "$output_file" --write-out '%{http_code}' "$@" || true
}

_print_summary() {
  printf '\n=== Deep prod smoke summary (%s) ===\n' "$APP_URL"
  local row status label
  for row in "${RESULTS[@]+"${RESULTS[@]}"}"; do
    status="${row%%|*}"
    label="${row#*|}"
    printf '  %-4s %s\n' "$status" "$label"
  done
  printf 'Totals: pass=%s fail=%s warn=%s\n' "$PASS" "$FAIL" "$WARN"
}

printf 'CurieAI deep production smoke: %s\n' "$APP_URL"

# ── Phase A: public ──────────────────────────────────────────────────────────
ROOT_CODE="$(request_code "$TMP_DIR/root.html" "$PUBLIC_TIMEOUT" "$APP_URL/")"
[[ "$ROOT_CODE" == "200" ]] || fail_hard "app shell returned HTTP $ROOT_CODE"
grep -qi '<title>CurieAI</title>' "$TMP_DIR/root.html" || fail_hard "app shell is missing CurieAI title"
pass "app shell"

HEALTH_CODE="$(request_code "$TMP_DIR/health.json" "$PUBLIC_TIMEOUT" "$APP_URL/health")"
READY_CODE="$(request_code "$TMP_DIR/ready.json" "$PUBLIC_TIMEOUT" "$APP_URL/ready")"
AUTH_CONFIG_CODE="$(request_code "$TMP_DIR/auth-config.json" "$PUBLIC_TIMEOUT" "$APP_URL/auth/config")"
[[ "$HEALTH_CODE" == "200" ]] || fail_hard "/health returned HTTP $HEALTH_CODE"
[[ "$READY_CODE" == "200" ]] || fail_hard "/ready returned HTTP $READY_CODE"
[[ "$AUTH_CONFIG_CODE" == "200" ]] || fail_hard "/auth/config returned HTTP $AUTH_CONFIG_CODE"
pass "/health"
pass "/ready"
pass "/auth/config"

python3 - "$TMP_DIR/health.json" "$TMP_DIR/auth-config.json" <<'PY' || fail_hard "health/auth-config payload invalid"
import json
import sys

health = json.load(open(sys.argv[1], encoding="utf-8"))
auth = json.load(open(sys.argv[2], encoding="utf-8"))
if health.get("status") != "ok":
    raise SystemExit("health status != ok")
required = {"auth_disabled", "google_auth_enabled", "signup_mode"}
missing = sorted(required - auth.keys())
if missing:
    raise SystemExit(f"auth/config missing keys: {', '.join(missing)}")
PY
pass "health + auth-config payloads"

# ── Phase B: authenticated workflow matrix ───────────────────────────────────
[[ -n "$AUTH_TOKEN" ]] || fail_hard "AUTH_TOKEN (or PROD_SMOKE_AUTH_TOKEN) is required for deep smoke"

AUTH_HEADER="Authorization: Bearer $AUTH_TOKEN"
SMOKE_TAG="PROD_DEEP_SMOKE $(date -u +%Y%m%dT%H%M%SZ)"

ME_CODE="$(request_code "$TMP_DIR/me.json" "$PUBLIC_TIMEOUT" -H "$AUTH_HEADER" "$APP_URL/auth/me")"
[[ "$ME_CODE" == "200" ]] || fail_hard "/auth/me returned HTTP $ME_CODE (token expired or invalid?)"
python3 - "$TMP_DIR/me.json" <<'PY' || fail_hard "/auth/me payload invalid"
import json
import sys

user = json.load(open(sys.argv[1], encoding="utf-8"))
if not user.get("id"):
    raise SystemExit("missing user id")
email = user.get("email") or user.get("display_name") or user["id"]
print(f"authenticated as {email}")
PY
pass "/auth/me"

CONV_CODE="$(request_code "$TMP_DIR/conv.json" "$PUBLIC_TIMEOUT" \
  -X POST \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  --data "{\"title\":\"$SMOKE_TAG\"}" \
  "$APP_URL/conversations")"
[[ "$CONV_CODE" == "201" || "$CONV_CODE" == "200" ]] || fail_hard "POST /conversations returned HTTP $CONV_CODE"
CONV_ID="$(python3 - "$TMP_DIR/conv.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("id") or "")
PY
)"
[[ -n "$CONV_ID" ]] || fail_hard "POST /conversations missing id"
pass "POST /conversations ($CONV_ID)"

chat_case() {
  local name="$1"
  local path="$2"
  local body_file="$3"
  local out="$TMP_DIR/${name}.json"
  local code
  code="$(request_code "$out" "$CHAT_TIMEOUT" \
    -X POST \
    -H "$AUTH_HEADER" \
    -H 'Content-Type: application/json' \
    --data @"$body_file" \
    "$APP_URL$path")"
  if [[ "$code" != "200" ]]; then
    local detail
    detail="$(python3 - "$out" <<'PY' 2>/dev/null || true
import json, sys
try:
    p = json.load(open(sys.argv[1], encoding="utf-8"))
    print(str(p.get("detail") or p.get("message") or p)[:240])
except Exception:
    print(open(sys.argv[1], encoding="utf-8").read()[:240])
PY
)"
    fail_soft "$name → HTTP $code${detail:+ ($detail)}"
    return 1
  fi
  if ! python3 - "$out" "$name" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
name = sys.argv[2]
msg = str(payload.get("message") or "").strip()
if not msg:
    raise SystemExit("empty assistant message")
# Soft signal for orchestrated / workflow metadata
meta_bits = []
if payload.get("reasoning"):
    meta_bits.append("reasoning")
if payload.get("workflow"):
    meta_bits.append("workflow")
if payload.get("planned_tools"):
    meta_bits.append("planned_tools")
if payload.get("live"):
    meta_bits.append("live")
suffix = f" [{', '.join(meta_bits)}]" if meta_bits else ""
print(f"{name}: {len(msg)} chars{suffix}")
if name.startswith("orchestrated") and not meta_bits:
    # Non-fatal: orchestrated may still answer without exposing metadata fields.
    print("SOFT_WARN_NO_META", file=sys.stderr)
PY
  then
    fail_soft "$name → empty or invalid response body"
    return 1
  fi
  local soft
  soft="$(python3 - "$out" "$name" <<'PY' 2>/dev/null || true
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
name = sys.argv[2]
if name.startswith("orchestrated") and not (payload.get("reasoning") or payload.get("workflow")):
    print("warn")
PY
)"
  if [[ "$soft" == "warn" ]]; then
    warn "$name → reply ok but no reasoning/workflow metadata"
  fi
  pass "$name"
  return 0
}

# Fast
python3 - "$TMP_DIR/body_fast.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: hello in one sentence",
    "options": {"force_strategy": "fast"},
}, open(path, "w", encoding="utf-8"))
PY
chat_case "fast /chat" "/chat" "$TMP_DIR/body_fast.json" || true

# Tools (live-ish)
python3 - "$TMP_DIR/body_tools.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: What is the weather in Austin, Texas right now? One short sentence.",
    "options": {"force_strategy": "tools"},
}, open(path, "w", encoding="utf-8"))
PY
chat_case "tools /chat" "/chat" "$TMP_DIR/body_tools.json" || true

# Orchestrated
python3 - "$TMP_DIR/body_orch.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: In two short bullets, summarize why HTTPS matters for web apps.",
    "options": {"force_strategy": "orchestrated"},
}, open(path, "w", encoding="utf-8"))
PY
chat_case "orchestrated /chat" "/chat" "$TMP_DIR/body_orch.json" || true

# Smart — greeting
python3 - "$TMP_DIR/body_smart_hi.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: hi",
}, open(path, "w", encoding="utf-8"))
PY
chat_case "smart_chat greeting" "/smart_chat" "$TMP_DIR/body_smart_hi.json" || true

# Smart — heavier
python3 - "$TMP_DIR/body_smart_heavy.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: Compare TCP and UDP in three short bullets.",
}, open(path, "w", encoding="utf-8"))
PY
chat_case "smart_chat heavy" "/smart_chat" "$TMP_DIR/body_smart_heavy.json" || true

# Stream
python3 - "$TMP_DIR/body_stream.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: Reply with exactly: STREAM_OK",
    "options": {"force_strategy": "fast"},
}, open(path, "w", encoding="utf-8"))
PY
STREAM_CODE="$(request_code "$TMP_DIR/stream.txt" "$CHAT_TIMEOUT" \
  -X POST \
  -H "$AUTH_HEADER" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  --data @"$TMP_DIR/body_stream.json" \
  "$APP_URL/chat/stream")"
if [[ "$STREAM_CODE" != "200" ]]; then
  fail_soft "chat/stream → HTTP $STREAM_CODE"
else
  if python3 - "$TMP_DIR/stream.txt" <<'PY'
import json
import sys

raw = open(sys.argv[1], encoding="utf-8").read()
if "data:" not in raw:
    raise SystemExit("no SSE data: lines")
saw_final = False
message = ""
for line in raw.splitlines():
    if not line.startswith("data:"):
        continue
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        continue
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        continue
    if event.get("type") == "final":
        saw_final = True
        response = event.get("response") or {}
        message = str(response.get("message") or "").strip()
        break
    if event.get("type") == "error":
        raise SystemExit(f"stream error event: {event}")
if not saw_final:
    raise SystemExit("no final SSE event")
if not message:
    raise SystemExit("final event had empty message")
print(f"stream final message length={len(message)}")
PY
  then
    pass "chat/stream"
  else
    fail_soft "chat/stream → missing final SSE message"
  fi
fi

# Workflow chat (light)
python3 - "$TMP_DIR/body_workflow.json" "$CONV_ID" "$SMOKE_TAG" <<'PY'
import json, sys
path, conv_id, tag = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({
    "conversation_id": conv_id,
    "message": f"{tag}: Give one sentence on what a smoke test is.",
    "workflow": {"enabled": True, "use_rag": False, "include_trace": True, "max_steps": 4},
}, open(path, "w", encoding="utf-8"))
PY
chat_case "workflow_chat" "/workflow_chat" "$TMP_DIR/body_workflow.json" || true

_print_summary
if [[ "$FAIL" -gt 0 ]]; then
  printf 'Deep production smoke FAILED\n' >&2
  exit 1
fi
printf 'Deep production smoke passed\n'
exit 0
