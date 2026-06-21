#!/usr/bin/env bash
# Smoke-test live external providers and the running Personal AI HTTP API.
# Usage:
#   ./scripts/real_api_smoke.sh
#   BASE_URL=http://127.0.0.1:8000 ./scripts/real_api_smoke.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

pass() { printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '  ✗ %s\n' "$1"; FAIL=$((FAIL + 1)); }

check_http() {
  local name="$1"
  local url="$2"
  local expect="${3:-200}"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "$url" || true)"
  if [[ "$code" == "$expect" ]]; then
    pass "$name (HTTP $code)"
  else
    fail "$name (expected $expect, got $code)"
  fi
}

check_json_field() {
  local name="$1"
  local payload="$2"
  local expr="$3"
  if printf '%s' "$payload" | python3 -c "import json,sys; d=json.load(sys.stdin); assert ($expr)" 2>/dev/null; then
    pass "$name"
  else
    fail "$name"
    printf '    response: %s\n' "$(printf '%s' "$payload" | head -c 400)"
  fi
}

printf '\n=== Provider probes (no app DB required) ===\n'
cd "$ROOT_DIR"
if python3 - <<'PY'
import asyncio, sys
sys.path.insert(0, ".")
from app.core.config import Settings
from app.services.adapter_cache import InMemoryAdapterCache
from app.services.geocoding import GeocodingService
from app.services.live_data_manager import LiveDataManager
from app.services.market_data import YahooMarketDataProvider
from app.services.web_search import WebSearchService

async def main() -> None:
    web = WebSearchService()
    fx = await web.get_live_fx_rate("USD", "INR")
    assert fx and fx.get("rate"), fx
    print("fx_ok", fx["rate"])

    geo = GeocodingService(cache=InMemoryAdapterCache())
    loc = await geo.resolve("Austin, TX")
    assert loc and loc.get("latitude"), loc
    print("geo_ok", loc.get("name"))

    yahoo = YahooMarketDataProvider(timeout=15)
    quote = await yahoo.get_stock_quote("MSFT")
    assert quote and quote.get("price"), quote
    print("stock_ok", quote["price"])

    manager = LiveDataManager(web_search=web, cache=InMemoryAdapterCache(), settings=Settings())
    result = await manager.resolve("usd to inr")
    assert result and result.verified, result
    print("manager_ok", result.domain, result.source)

asyncio.run(main())
PY
then
  pass "Frankfurter FX + geocoding + Yahoo quote + LiveDataManager"
else
  fail "Provider probe script"
fi

printf '\n=== HTTP API (%s) ===\n' "$BASE_URL"
check_http "GET /health" "$BASE_URL/health" 200

ready="$(curl -s "$BASE_URL/ready" || true)"
if printf '%s' "$ready" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ready' else 1)" 2>/dev/null; then
  pass "GET /ready (all dependencies up)"
else
  fail "GET /ready (ollama/qdrant may be down — start: make up)"
  printf '    %s\n' "$(printf '%s' "$ready" | head -c 300)"
fi

chat_fx="$(curl -s -X POST "$BASE_URL/chat" -H 'Content-Type: application/json' -d '{"message":"usd to inr"}' || true)"
if printf '%s' "$chat_fx" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('live',{}).get('domain')=='fx' and d.get('live',{}).get('verified')" 2>/dev/null; then
  pass "POST /chat live FX short-circuit with provenance"
else
  code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/chat" -H 'Content-Type: application/json' -d '{"message":"usd to inr"}' || true)"
  fail "POST /chat live FX (HTTP $code — is Postgres migrated? run: make db-migrate)"
  printf '    %s\n' "$(printf '%s' "$chat_fx" | head -c 300)"
fi

weather="$(curl -s -X POST "$BASE_URL/chat" -H 'Content-Type: application/json' -d '{"message":"weather in Austin"}' || true)"
check_json_field "POST /chat weather" "$weather" "d.get('live',{}).get('domain') in ('weather_current','weather_forecast') or 'WEATHER' in d.get('message','').upper()"

printf '\n=== Summary: %s passed, %s failed ===\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
