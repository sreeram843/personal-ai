from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import httpx

from app.services.adapter_cache import AdapterCache
from app.schemas.adapter import AdapterResult

logger = logging.getLogger(__name__)


class GeocodingService:
    """Resolve place names to coordinates via Open-Meteo with optional cache."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        cache: AdapterCache | None = None,
        cache_ttl_seconds: int = 86_400,
    ) -> None:
        self._timeout = timeout
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def resolve(self, location: str) -> Optional[Dict[str, Any]]:
        place = location.strip()
        if not place:
            return None

        cache_key = f"geocode:{place.lower()}"
        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached is not None and cached.status == "ok":
                return dict(cached.data)

        coords = _parse_lat_lon(place)
        if coords is not None:
            payload = await self._reverse(*coords)
            if payload is not None:
                await self._store_cache(cache_key, payload)
                return payload

        candidates = [place]
        no_state_abbrev = re.sub(r",\s*[A-Z]{2}\b", "", place)
        if no_state_abbrev and no_state_abbrev != place:
            candidates.append(no_state_abbrev.strip())
        if "," in place:
            first_segment = place.split(",", 1)[0].strip()
            if first_segment and first_segment not in candidates:
                candidates.append(first_segment)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                for candidate in candidates:
                    response = await client.get(
                        "https://geocoding-api.open-meteo.com/v1/search",
                        params={"name": candidate, "count": 1, "language": "en", "format": "json"},
                    )
                    response.raise_for_status()
                    results = response.json().get("results") or []
                    if results:
                        payload = results[0]
                        await self._store_cache(cache_key, payload)
                        return payload
        except Exception as exc:
            logger.warning("Geocode failed for '%s': %s", place, exc)
            return None

        return None

    async def _reverse(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/reverse",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "language": "en",
                        "format": "json",
                    },
                )
                response.raise_for_status()
                results = response.json().get("results") or []
                if results:
                    return results[0]
        except Exception as exc:
            logger.warning("Reverse geocode failed for %s,%s: %s", latitude, longitude, exc)
        return None

    async def _store_cache(self, cache_key: str, payload: Dict[str, Any]) -> None:
        if self._cache is None:
            return
        await self._cache.set(
            cache_key,
            AdapterResult(
                domain="geocode",
                status="ok",
                verified=True,
                source="Open-Meteo Geocoding",
                fetched_at_utc=_utc_now(),
                ttl_seconds=self._cache_ttl_seconds,
                data=payload,
                confidence=0.95,
            ),
            self._cache_ttl_seconds,
        )


def _parse_lat_lon(value: str) -> Optional[tuple[float, float]]:
    match = re.fullmatch(
        r"\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*",
        value,
    )
    if not match:
        return None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if abs(lat) > 90 or abs(lon) > 180:
        return None
    return lat, lon


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_place_label(geo: Dict[str, Any], fallback: str) -> str:
    """Prefer a human place name over raw coordinates."""
    name = str(geo.get("name") or "").strip()
    if not name or _parse_lat_lon(name) is not None:
        name = fallback.strip() if fallback.strip() and _parse_lat_lon(fallback) is None else name
    parts = [part for part in [name, geo.get("admin1"), geo.get("country")] if part]
    if parts:
        return ", ".join(str(part) for part in parts)
    return fallback.strip() or "Unknown location"


__all__ = ["GeocodingService", "format_place_label"]
