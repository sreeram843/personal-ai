from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_CRYPTO_IDS: dict[str, str] = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "sol": "solana",
    "solana": "solana",
    "xrp": "ripple",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
    "ada": "cardano",
    "cardano": "cardano",
}

_SERVICE_STATUS_URLS: dict[str, str] = {
    "github": "https://www.githubstatus.com/api/v2/status.json",
    "aws": "https://health.aws.amazon.com/health/status.json",
    "cloudflare": "https://www.cloudflarestatus.com/api/v2/status.json",
    "openai": "https://status.openai.com/api/v2/status.json",
    "slack": "https://status.slack.com/api/v2.0.0/current",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def detect_crypto_symbol(query: str) -> Optional[Tuple[str, str]]:
    """Return (coingecko_id, display_label) when query mentions a supported crypto."""
    text = query.lower()
    for keyword, coin_id in _CRYPTO_IDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            label = keyword.upper() if len(keyword) <= 5 else keyword.title()
            return coin_id, label
    symbol_match = re.search(r"\b([A-Z]{2,5})\b", query)
    if symbol_match:
        sym = symbol_match.group(1).lower()
        if sym in _CRYPTO_IDS:
            return _CRYPTO_IDS[sym], sym.upper()
    return None


async def _geocode(location: str, *, timeout: float = 10.0) -> Optional[dict]:
    loc = location.strip()
    if not loc:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": loc, "count": 1, "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            return results[0] if results else None
    except Exception:
        logger.exception("Geocoding failed for %s", loc)
        return None


async def fetch_crypto_price(query: str, *, timeout: float = 10.0) -> Optional[dict]:
    detected = detect_crypto_symbol(query)
    if not detected:
        return None
    coin_id, label = detected
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_last_updated_at": "true",
                },
            )
            resp.raise_for_status()
            payload = resp.json().get(coin_id) or {}
            if "usd" not in payload:
                return None
            return {
                "symbol": label,
                "name": label,
                "coin_id": coin_id,
                "price": float(payload["usd"]),
                "currency": "USD",
                "change_percent": payload.get("usd_24h_change"),
                "asOf": _now_iso(),
                "source": "CoinGecko",
                "live": True,
                "subscription_key": f"crypto:{label}",
            }
    except Exception:
        logger.exception("CoinGecko fetch failed for %s", coin_id)
        return None


async def fetch_air_quality(location: str, *, timeout: float = 10.0) -> Optional[dict]:
    geo = await _geocode(location, timeout=timeout)
    if not geo:
        return None
    lat = geo.get("latitude")
    lon = geo.get("longitude")
    if lat is None or lon is None:
        return None
    name = geo.get("name") or location
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "us_aqi,pm2_5,pm10",
                },
            )
            resp.raise_for_status()
            current = resp.json().get("current") or {}
            return {
                "location": name,
                "usAqi": current.get("us_aqi"),
                "pm25": current.get("pm2_5"),
                "pm10": current.get("pm10"),
                "asOf": _now_iso(),
                "source": "Open-Meteo Air Quality",
                "live": False,
            }
    except Exception:
        logger.exception("Air quality fetch failed for %s", location)
        return None


async def fetch_sun_times(location: str, *, timeout: float = 10.0) -> Optional[dict]:
    geo = await _geocode(location, timeout=timeout)
    if not geo:
        return None
    lat = geo.get("latitude")
    lon = geo.get("longitude")
    if lat is None or lon is None:
        return None
    name = geo.get("name") or location
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "https://api.sunrise-sunset.org/json",
                params={"lat": lat, "lng": lon, "formatted": 0},
            )
            resp.raise_for_status()
            results = resp.json().get("results") or {}
            return {
                "location": name,
                "sunrise": results.get("sunrise"),
                "sunset": results.get("sunset"),
                "solarNoon": results.get("solar_noon"),
                "dayLengthSeconds": results.get("day_length"),
                "asOf": _now_iso(),
                "source": "sunrise-sunset.org",
                "live": False,
            }
    except Exception:
        logger.exception("Sun times fetch failed for %s", location)
        return None


async def fetch_service_status(service: str, *, timeout: float = 10.0) -> Optional[dict]:
    key = service.strip().lower()
    key = re.sub(r"[^a-z0-9]", "", key)
    url = _SERVICE_STATUS_URLS.get(key)
    if not url:
        for alias, target in _SERVICE_STATUS_URLS.items():
            if alias in key or key in alias:
                url = target
                key = alias
                break
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()
            status = payload.get("status") or {}
            if isinstance(status, dict):
                indicator = status.get("indicator") or status.get("description") or "unknown"
                description = status.get("description") or indicator
            else:
                indicator = str(status)
                description = indicator
            return {
                "service": key,
                "status": indicator,
                "description": description,
                "asOf": _now_iso(),
                "source": f"{key} status page",
                "live": False,
            }
    except Exception:
        logger.exception("Service status fetch failed for %s", service)
        return None


def stub_provider_payload(kind: str, query: str, *, note: str) -> Dict[str, Any]:
    return {
        "kind": kind,
        "query": query,
        "status": "not_configured",
        "message": note,
        "asOf": _now_iso(),
        "source": "Personal AI",
        "live": False,
    }


__all__ = [
    "detect_crypto_symbol",
    "fetch_air_quality",
    "fetch_crypto_price",
    "fetch_service_status",
    "fetch_sun_times",
    "stub_provider_payload",
]
