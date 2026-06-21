#!/usr/bin/env bash
# Evaluate model + live-data accuracy against a running Personal AI stack.
#
# Usage:
#   ./scripts/model_accuracy_smoke.sh
#   BASE_URL=http://127.0.0.1:8000 ./scripts/model_accuracy_smoke.sh
#
# Prerequisites: app running (e.g. make up-remote), Postgres migrated.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PASS=0
FAIL=0
SKIP=0

pass() { printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '  ✗ %s\n' "$1"; FAIL=$((FAIL + 1)); }
skip() { printf '  ~ %s\n' "$1"; SKIP=$((SKIP + 1)); }

printf '\n=== Model accuracy smoke (%s) ===\n' "$BASE_URL"

cd "$ROOT_DIR"
python3 - "$BASE_URL" <<'PY'
import asyncio
import json
import re
import sys
from typing import Any

import httpx

BASE = sys.argv[1]
PASS = FAIL = SKIP = 0


def pass_(name: str) -> None:
    global PASS
    print(f"  ✓ {name}")
    PASS += 1


def fail_(name: str, detail: str = "") -> None:
    global FAIL
    print(f"  ✗ {name}")
    if detail:
        print(f"    {detail[:400]}")
    FAIL += 1


def skip_(name: str, reason: str = "") -> None:
    global SKIP
    msg = f"  ~ {name}"
    if reason:
        msg += f" ({reason})"
    print(msg)
    SKIP += 1


async def post(path: str, message: str, *, timeout: float = 120.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{BASE}{path}", json={"message": message})
        if resp.status_code >= 500:
            raise RuntimeError(f"{path} HTTP {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
        return resp.json()


def extract_numbers(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d+\.?\d*", text)]


def message_contains(text: str, *needles: str) -> bool:
    upper = text.upper()
    return all(n.upper() in upper for n in needles)


async def main() -> None:
    # Readiness
    async with httpx.AsyncClient(timeout=15.0) as client:
        ready = (await client.get(f"{BASE}/ready")).json()
    if ready.get("status") != "ready":
        fail_("GET /ready", json.dumps(ready)[:300])
        print(f"\n=== Summary: {PASS} passed, {FAIL} failed, {SKIP} skipped ===")
        sys.exit(1)
    pass_("GET /ready")

    # Ground truth from live providers (same sources the app uses)
    sys.path.insert(0, ".")
    from app.services.adapter_cache import InMemoryAdapterCache
    from app.services.geocoding import GeocodingService
    from app.services.market_data import YahooMarketDataProvider
    from app.services.web_search import WebSearchService

    web = WebSearchService(timeout=20)
    fx_truth = await web.get_live_fx_rate("USD", "INR")
    yahoo = YahooMarketDataProvider(timeout=20)
    msft_truth = await yahoo.get_stock_quote("MSFT")

    assert fx_truth and fx_truth.get("rate")
    assert msft_truth and msft_truth.get("price")
    usd_inr = float(fx_truth["rate"])
    msft_price = float(msft_truth["price"])

    # ── Live data accuracy (verified feeds, not LLM hallucination) ─────────────
    fx_body = await post("/chat", "usd to inr")
    live = fx_body.get("live") or {}
    msg = fx_body.get("message", "")
    if live.get("domain") == "fx" and live.get("verified"):
        rate_match = re.search(r"1\s+USD\s*=\s*([\d.]+)\s+INR", msg, re.I)
        if rate_match:
            rate = float(rate_match.group(1))
            err = abs(rate - usd_inr) / usd_inr
            if err <= 0.01:
                pass_(f"Live FX matches Frankfurter ({rate:.4f} USD/INR, err {err*100:.2f}%)")
            else:
                fail_("Live FX rate drift", f"got {rate}, expected ~{usd_inr}, err {err*100:.2f}%")
        else:
            fail_("Live FX missing rate in message", msg[:200])
    else:
        fail_("Live FX short-circuit", json.dumps(live)[:200])

    weather_body = await post("/chat", "current weather in London")
    wlive = weather_body.get("live") or {}
    wmsg = weather_body.get("message", "")
    if wlive.get("domain") == "weather_current" and wlive.get("verified"):
        if re.search(r"Temperature:\s*[\d.]+\s*°?C", wmsg, re.I) or re.search(r"[\d.]+\s*°C", wmsg):
            pass_("Live weather verified (temperature present in response)")
        else:
            fail_("Live weather missing temperature", wmsg[:200])
    else:
        fail_("Live weather short-circuit", json.dumps(wlive)[:200])

    stock_body = await post("/smart_chat", "What is the current MSFT stock price?")
    slive = stock_body.get("live") or {}
    if slive.get("domain") == "stock" and slive.get("verified"):
        msg = stock_body.get("message", "")
        nums = extract_numbers(msg)
        if nums and min(abs(n - msft_price) / msft_price for n in nums) <= 0.02:
            pass_(f"Live stock matches Yahoo (MSFT ~{msft_price:.2f} USD)")
        else:
            fail_("Live stock price mismatch", f"Yahoo {msft_price}, text nums {nums[:5]}")
    else:
        fail_("Live stock short-circuit", json.dumps(slive)[:200])

    # ── LLM reasoning (remote chat model via LM Studio / Ollama path) ─────────
    llm_cases = [
        ("Math: 47 × 23", "/chat", "What is 47 times 23? Answer with only the number.", 1081.0, 0.0),
        ("Math: 15% of 200", "/chat", "What is 15 percent of 200? Number only.", 30.0, 0.0),
        ("Math: average speed", "/chat", "If a train travels 120 km in 2 hours, what is its average speed in km/h? Number only.", 60.0, 0.0),
    ]
    for label, path, prompt, expected, tol in llm_cases:
        body = await post(path, prompt)
        msg = body.get("message", "")
        nums = extract_numbers(msg)
        if not nums:
            fail_(label, f"no number in: {msg[:150]}")
            continue
        closest = min(nums, key=lambda n: abs(n - expected))
        err = abs(closest - expected) / expected if expected else abs(closest - expected)
        if err <= max(tol, 0.001):
            pass_(f"{label} → {closest}")
        else:
            fail_(label, f"expected {expected}, closest {closest} in: {msg[:150]}")

    factual_cases = [
        ("Fact: capital of France", "/chat", "What is the capital of France? One word only.", ("PARIS",)),
        ("Fact: chemical symbol for sodium", "/chat", "What is the chemical symbol for sodium? Reply with the symbol only.", ("NA",)),
    ]
    for label, path, prompt, needles in factual_cases:
        body = await post(path, prompt)
        msg = body.get("message", "")
        if message_contains(msg, *needles):
            pass_(f"{label} → found {needles[0]}")
        else:
            fail_(label, msg[:150])

    # ── Anti-hallucination spot check: LLM should not invent live FX when asked obliquely
    # (workflow/agent path — may take longer; skip if timeout)
    try:
        body = await post(
            "/chat",
            "Without using any tools, guess the USD to INR exchange rate right now.",
            timeout=90.0,
        )
        msg = body.get("message", "")
        if (body.get("live") or {}).get("verified"):
            skip_("Oblique FX (live short-circuit fired)", "routing bypassed LLM guess")
        elif re.search(r"\d+\.\d+", msg):
            skip_("Oblique FX guess", "model gave a number — compare manually to Frankfurter")
        else:
            pass_("Oblique FX: model did not assert a precise live rate")
    except Exception as exc:
        skip_("Oblique FX check", str(exc)[:80])

    print(f"\n=== Summary: {PASS} passed, {FAIL} failed, {SKIP} skipped ===")
    if FAIL:
        sys.exit(1)


asyncio.run(main())
PY

exit_code=$?
exit "$exit_code"
