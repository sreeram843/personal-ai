#!/usr/bin/env bash
# Quick auth/OAuth diagnostics against a running app (default: local prod port).
#
# Usage:
#   ./scripts/verify_prod_auth.sh
#   APP_URL=https://curai.example.com ./scripts/verify_prod_auth.sh

set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"
APP_URL="${APP_URL%/}"

printf 'Checking auth config at %s/auth/config\n' "$APP_URL"
BODY=$(curl -fsS "$APP_URL/auth/config")
echo "$BODY" | python3 -m json.tool

AUTH_DISABLED=$(echo "$BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('auth_disabled'))")
GOOGLE_ENABLED=$(echo "$BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('google_auth_enabled'))")
CLIENT_ID=$(echo "$BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('google_client_id') or '')")

echo
if [ "$AUTH_DISABLED" = "True" ] || [ "$AUTH_DISABLED" = "true" ]; then
  printf 'WARN: AUTH_DISABLED=true — app skips Google login and uses dev auto-token.\n'
  printf '      Set AUTH_DISABLED=false in .env.cloud and redeploy for OAuth.\n'
fi

if [ "$GOOGLE_ENABLED" != "True" ] && [ "$GOOGLE_ENABLED" != "true" ]; then
  printf 'WARN: google_auth_enabled=false — login page will not show Google Sign-In.\n'
  printf '      Set GOOGLE_CLIENT_ID in .env.cloud and AUTH_DISABLED=false, then redeploy.\n'
else
  printf 'OK: Google Sign-In is enabled (client_id=%s...)\n' "${CLIENT_ID:0:20}"
  printf '     Ensure Google Cloud "Authorized JavaScript origins" includes: %s\n' "$APP_URL"
fi

UNAUTH_CODE=$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/auth/me")
if [ "$AUTH_DISABLED" = "False" ] || [ "$AUTH_DISABLED" = "false" ]; then
  if [ "$UNAUTH_CODE" = "401" ]; then
    printf 'OK: /auth/me returns 401 without token (auth enforced).\n'
  else
    printf 'WARN: expected /auth/me -> 401 when auth enabled, got %s\n' "$UNAUTH_CODE"
  fi
fi
