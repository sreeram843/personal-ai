from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Dict, Optional

from app.core.config import Settings
from app.schemas.adapter import AdapterResult

logger = logging.getLogger(__name__)


class AdapterCache:
    async def get(self, key: str) -> Optional[AdapterResult]:
        raise NotImplementedError

    async def set(self, key: str, value: AdapterResult, ttl_seconds: int) -> None:
        raise NotImplementedError


@dataclass
class _InMemoryRecord:
    value: AdapterResult
    expires_at: datetime


class InMemoryAdapterCache(AdapterCache):
    def __init__(self) -> None:
        self._store: Dict[str, _InMemoryRecord] = {}
        self._lock: Optional[asyncio.Lock] = None

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get(self, key: str) -> Optional[AdapterResult]:
        now = datetime.now(timezone.utc)
        async with self._ensure_lock():
            record = self._store.get(key)
            if not record:
                return None
            if record.expires_at <= now:
                self._store.pop(key, None)
                return None
            return record.value

    async def set(self, key: str, value: AdapterResult, ttl_seconds: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl_seconds, 1))
        async with self._ensure_lock():
            self._store[key] = _InMemoryRecord(value=value, expires_at=expires_at)


class RedisAdapterCache(AdapterCache):
    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis  # lazy import

        self._client = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> Optional[AdapterResult]:
        payload = await self._client.get(key)
        if not payload:
            return None
        try:
            data = json.loads(payload)
            return AdapterResult(**data)
        except Exception:
            return None

    async def set(self, key: str, value: AdapterResult, ttl_seconds: int) -> None:
        await self._client.set(key, value.model_dump_json(), ex=max(ttl_seconds, 1))


def build_adapter_cache(settings: Settings) -> AdapterCache:
    """Create cache backend according to settings, with safe fallbacks."""
    if not settings.enable_adapter_cache:
        return InMemoryAdapterCache()

    backend = settings.adapter_cache_backend.lower().strip()
    if backend == "redis" and settings.redis_url:
        try:
            return RedisAdapterCache(settings.redis_url)
        except Exception as exc:
            logger.warning("Redis cache init failed; falling back to in-memory cache: %s", exc)
            return InMemoryAdapterCache()

    return InMemoryAdapterCache()


__all__ = ["AdapterCache", "InMemoryAdapterCache", "RedisAdapterCache", "build_adapter_cache"]
