"""Tests for in-memory demo question quota."""

import asyncio

import pytest

import app.services.demo_quota as demo_quota_module
from app.services.demo_quota import InMemoryDemoQuotaStore


@pytest.fixture
def store() -> InMemoryDemoQuotaStore:
    demo_quota_module._demo_quota_store = None
    return InMemoryDemoQuotaStore(ttl_hours=1)


def test_increment_tracks_usage(store: InMemoryDemoQuotaStore) -> None:
    assert asyncio.run(store.get_usage("session-a")) == 0

    first = asyncio.run(store.increment("session-a", max_questions=5))
    assert first.used == 1
    assert first.remaining == 4
    assert first.limit_reached is False

    assert asyncio.run(store.get_usage("session-a")) == 1


def test_limit_reached_at_max(store: InMemoryDemoQuotaStore) -> None:
    snapshot = None
    for _ in range(5):
        snapshot = asyncio.run(store.increment("session-b", max_questions=5))
    assert snapshot is not None
    assert snapshot.used == 5
    assert snapshot.remaining == 0
    assert snapshot.limit_reached is True

    blocked = asyncio.run(store.increment("session-b", max_questions=5))
    assert blocked.used == 5
    assert blocked.remaining == 0
    assert blocked.limit_reached is True


def test_sessions_are_isolated(store: InMemoryDemoQuotaStore) -> None:
    asyncio.run(store.increment("one", max_questions=3))
    asyncio.run(store.increment("one", max_questions=3))
    assert asyncio.run(store.get_usage("one")) == 2
    assert asyncio.run(store.get_usage("two")) == 0
