from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.schemas.adapter import AdapterResult
from app.services import adapter_cache as adapter_cache_module
from app.services.adapter_cache import InMemoryAdapterCache, build_adapter_cache


def _sample_result() -> AdapterResult:
    return AdapterResult(
        domain="fx",
        status="ok",
        verified=True,
        source="Frankfurter API",
        fetched_at_utc="2026-03-22 23:58:00 UTC",
        ttl_seconds=1,
        data={"base": "USD", "quote": "INR", "rate": 93.62},
    )


def test_in_memory_cache_expires_items() -> None:
    cache = InMemoryAdapterCache()

    asyncio.run(cache.set("fx", _sample_result(), ttl_seconds=1))
    assert asyncio.run(cache.get("fx")) is not None

    asyncio.run(asyncio.sleep(1.1))
    assert asyncio.run(cache.get("fx")) is None


def test_build_adapter_cache_uses_in_memory_when_disabled() -> None:
    cache = build_adapter_cache(Settings(enable_adapter_cache=False))
    assert isinstance(cache, InMemoryAdapterCache)


def test_build_adapter_cache_falls_back_to_memory_if_redis_init_fails(monkeypatch) -> None:
    def broken_redis_cache(redis_url: str):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(adapter_cache_module, "RedisAdapterCache", broken_redis_cache)
    cache = build_adapter_cache(
        Settings(enable_adapter_cache=True, adapter_cache_backend="redis", redis_url="redis://localhost:6379/0")
    )

    assert isinstance(cache, InMemoryAdapterCache)