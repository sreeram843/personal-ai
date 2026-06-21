"""Property-style tenant isolation checks across stores."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from app.services.run_store import RunStore
from app.services.workflow_memory import WorkflowMemoryStore


USER_PAIRS = [
    ("user-alpha", "user-beta"),
    ("tenant-1", "tenant-2"),
    ("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"),
]

CONVERSATION_IDS = ["conv-a", "conv-b", "shared-conv-id"]


@pytest.mark.parametrize("user_a,user_b", USER_PAIRS)
def test_run_store_never_leaks_across_users(user_a: str, user_b: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run_a = store.create_run(mode="workflow", conversation_id="conv-1", user_id=user_a)
        run_b = store.create_run(mode="workflow", conversation_id="conv-1", user_id=user_b)

        assert store.get_run(run_a.run_id, user_id=user_a) is not None
        assert store.get_run(run_a.run_id, user_id=user_b) is None
        assert store.get_run(run_b.run_id, user_id=user_b) is not None
        assert store.get_run(run_b.run_id, user_id=user_a) is None

        listed_a = store.list_runs_by_conversation("conv-1", user_id=user_a)
        listed_b = store.list_runs_by_conversation("conv-1", user_id=user_b)
        assert {run.run_id for run in listed_a} == {run_a.run_id}
        assert {run.run_id for run in listed_b} == {run_b.run_id}


@pytest.mark.parametrize(
    "user_a,user_b,conversation_id",
    [(user_a, user_b, conversation_id) for user_a, user_b in USER_PAIRS for conversation_id in CONVERSATION_IDS],
)
def test_workflow_memory_namespaces_do_not_collide(
    user_a: str,
    user_b: str,
    conversation_id: str,
    tmp_path: Path,
) -> None:
    store = WorkflowMemoryStore(file_path=str(tmp_path / "memory.json"))

    async def run() -> None:
        await store.append_entries(
            conversation_id,
            [{"agent": "writer", "title": "note", "summary": f"secret for {user_a}"}],
            user_id=user_a,
        )
        await store.append_entries(
            conversation_id,
            [{"agent": "writer", "title": "note", "summary": f"secret for {user_b}"}],
            user_id=user_b,
        )
        summary_a = await store.get_summary(conversation_id, user_id=user_a)
        summary_b = await store.get_summary(conversation_id, user_id=user_b)
        assert f"secret for {user_a}" in summary_a
        assert f"secret for {user_b}" not in summary_a
        assert f"secret for {user_b}" in summary_b
        assert f"secret for {user_a}" not in summary_b

    asyncio.run(run())
