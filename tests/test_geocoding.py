"""Geocoding service tests."""

from __future__ import annotations

import asyncio

from app.schemas.adapter import AdapterResult
from app.services.geocoding import GeocodingService


class _RecordingCache:
    def __init__(self) -> None:
        self.stored: dict[str, AdapterResult] = {}

    async def get(self, key: str):
        return self.stored.get(key)

    async def set(self, key: str, value: AdapterResult, ttl_seconds: int) -> None:
        self.stored[key] = value


def test_geocoding_service_writes_cache_on_success(monkeypatch) -> None:
    cache = _RecordingCache()
    service = GeocodingService(cache=cache, cache_ttl_seconds=3600)

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"results": [{"name": "Austin", "latitude": 30.27, "longitude": -97.74}]}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            return _Resp()

    monkeypatch.setattr("app.services.geocoding.httpx.AsyncClient", lambda **kwargs: _Client())

    result = asyncio.run(service.resolve("Austin, TX"))
    assert result is not None
    assert result["name"] == "Austin"
    assert any(key.startswith("geocode:") for key in cache.stored)
