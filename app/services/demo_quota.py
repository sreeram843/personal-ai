from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple


@dataclass
class DemoQuotaSnapshot:
    used: int
    remaining: int
    limit_reached: bool


class DemoQuotaStore:
  async def get_usage(self, session_id: str) -> int:
    raise NotImplementedError

  async def increment(self, session_id: str, *, max_questions: int) -> DemoQuotaSnapshot:
    raise NotImplementedError


@dataclass
class _SessionRecord:
    count: int
    expires_at: datetime


class InMemoryDemoQuotaStore(DemoQuotaStore):
    """Track demo question counts per browser session (ephemeral, in-process)."""

    def __init__(self, *, ttl_hours: int = 24) -> None:
        self._ttl = timedelta(hours=ttl_hours)
        self._sessions: Dict[str, _SessionRecord] = {}
        self._lock: Optional[asyncio.Lock] = None

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _prune_expired(self, now: datetime) -> None:
        expired = [key for key, record in self._sessions.items() if record.expires_at <= now]
        for key in expired:
            self._sessions.pop(key, None)

    async def get_usage(self, session_id: str) -> int:
        now = datetime.now(timezone.utc)
        async with self._ensure_lock():
            self._prune_expired(now)
            record = self._sessions.get(session_id)
            return record.count if record else 0

    async def increment(self, session_id: str, *, max_questions: int) -> DemoQuotaSnapshot:
        now = datetime.now(timezone.utc)
        async with self._ensure_lock():
            self._prune_expired(now)
            record = self._sessions.get(session_id)
            if record is None:
                record = _SessionRecord(count=0, expires_at=now + self._ttl)
                self._sessions[session_id] = record

            if record.count >= max_questions:
                remaining = 0
                return DemoQuotaSnapshot(
                    used=record.count,
                    remaining=remaining,
                    limit_reached=True,
                )

            record.count += 1
            record.expires_at = now + self._ttl
            remaining = max(0, max_questions - record.count)
            return DemoQuotaSnapshot(
                used=record.count,
                remaining=remaining,
                limit_reached=record.count >= max_questions,
            )


_demo_quota_store: Optional[InMemoryDemoQuotaStore] = None


def get_demo_quota_store() -> InMemoryDemoQuotaStore:
    global _demo_quota_store
    if _demo_quota_store is None:
        _demo_quota_store = InMemoryDemoQuotaStore()
    return _demo_quota_store


__all__ = ["DemoQuotaSnapshot", "DemoQuotaStore", "InMemoryDemoQuotaStore", "get_demo_quota_store"]
