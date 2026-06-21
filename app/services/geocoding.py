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
                        if self._cache is not None:
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
                        return payload
        except Exception as exc:
            logger.warning("Geocode failed for '%s': %s", place, exc)
            return None

        return None


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


__all__ = ["GeocodingService"]
