"""Redis-backed run store tests."""

from __future__ import annotations

import pytest

from app.services.run_store import RedisRunStore, build_run_store


def test_build_run_store_uses_disk_by_default() -> None:
    store = build_run_store(storage_path="memory/runs", backend="disk", redis_url=None)
    assert store.__class__.__name__ == "RunStore"


@pytest.mark.skipif(True, reason="requires running Redis")
def test_redis_run_store_round_trip() -> None:
    store = RedisRunStore("redis://127.0.0.1:6379/15")
    run = store.create_run(mode="workflow", conversation_id="conv-1", user_id="user-1")
    loaded = store.get_run(run.run_id, user_id="user-1")
    assert loaded is not None
    assert loaded.conversation_id == "conv-1"
