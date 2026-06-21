"""Workflow memory isolation tests."""

from __future__ import annotations

import asyncio

from app.services.workflow_memory import WorkflowMemoryStore


def test_workflow_memory_is_scoped_per_user(tmp_path) -> None:
    store = WorkflowMemoryStore(file_path=str(tmp_path / "memory.json"))

    async def run() -> None:
        await store.append_entries(
            "conv-1",
            [{"agent": "planner", "title": "plan", "summary": "user-a plan"}],
            user_id="user-a",
        )
        await store.append_entries(
            "conv-1",
            [{"agent": "planner", "title": "plan", "summary": "user-b plan"}],
            user_id="user-b",
        )
        summary_a = await store.get_summary("conv-1", user_id="user-a")
        summary_b = await store.get_summary("conv-1", user_id="user-b")
        assert "user-a plan" in summary_a
        assert "user-b plan" not in summary_a
        assert "user-b plan" in summary_b
        assert "user-a plan" not in summary_b

    asyncio.run(run())
