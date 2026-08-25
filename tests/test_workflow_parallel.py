from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import patch

from app.schemas.chat import RetrievedChunk
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService, PlannedTask, TaskOutcome
from tests.llm_gateway_stub import LLMGatewayStubMixin


class _StubGateway(LLMGatewayStubMixin):
    async def generate(self, *, messages, model: str, options, provider=None):
        return "Final coordinated answer."


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _StubVectorStore:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None, query_text=None, hybrid=False):
        return []


class _StubWebSearch:
    async def search_with_page_excerpts(self, query: str):
        return []


class _StubWorkflowMemoryStore:
    async def get_summary(self, conversation_id: str, *, user_id: str | None = None, limit: int = 6) -> str:
        return ""

    async def append_entries(self, conversation_id: str, entries, *, user_id: str | None = None):
        return None


def _stub_model_profile() -> WorkflowModelProfile:
    stage = StageModelConfig(provider="ollama", model="test-model")
    return WorkflowModelProfile(
        planner=stage,
        synthesizer=stage,
        reviewer=stage,
        writer=stage,
    )


def _make_service() -> OrchestratedChatService:
    return OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=_StubGateway(),
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )


async def _run_timed_plan(plan: List[PlannedTask]) -> Dict[str, Dict[str, float]]:
    service = _make_service()
    timestamps: Dict[str, Dict[str, float]] = {}

    async def fake_plan(**kwargs: Any) -> tuple[List[PlannedTask], str]:
        return plan, "test plan"

    async def fake_execute(
        *,
        task: PlannedTask,
        state: Dict[str, Any],
        top_k: int,
        score_threshold: float | None,
        options: Dict[str, Any],
        use_rag: bool,
    ) -> TaskOutcome:
        timestamps[task.id] = {"start": time.monotonic()}
        await asyncio.sleep(0.08)
        timestamps[task.id]["end"] = time.monotonic()
        return TaskOutcome(status="completed", summary=f"{task.id} done")

    with patch.object(service, "_build_plan", side_effect=fake_plan):
        with patch.object(service, "_execute_task", side_effect=fake_execute):
            await service.run_mode(
                mode="workflow",
                query="Time overlapping independent workflow tasks.",
                system_prompt="You are a principled assistant.",
                chat_history=[],
                conversation_id="conversation-parallel",
                user_id="00000000-0000-0000-0000-0000000000cc",
                top_k=4,
                score_threshold=None,
                options={},
                use_rag=True,
                include_trace=True,
                persist_memory=False,
                max_steps=6,
            )
    return timestamps


def test_independent_ready_tasks_overlap_in_execution() -> None:
    plan = [
        PlannedTask(id="retrieve_context", agent="retriever", title="Retrieve", description="Internal docs."),
        PlannedTask(id="research_current_context", agent="researcher", title="Research", description="Web context."),
    ]
    timestamps = asyncio.run(_run_timed_plan(plan))

    first = timestamps["retrieve_context"]
    second = timestamps["research_current_context"]
    assert first["start"] < second["end"]
    assert second["start"] < first["end"]


def test_dependent_task_waits_for_dependency() -> None:
    plan = [
        PlannedTask(id="retrieve_context", agent="retriever", title="Retrieve", description="Internal docs."),
        PlannedTask(
            id="draft_answer",
            agent="synthesizer",
            title="Draft",
            description="Draft answer.",
            depends_on=["retrieve_context"],
        ),
    ]
    timestamps = asyncio.run(_run_timed_plan(plan))

    dependency = timestamps["retrieve_context"]
    dependent = timestamps["draft_answer"]
    assert dependency["end"] <= dependent["start"]


def test_parallel_retriever_researcher_merge_keeps_both_contexts() -> None:
    service = _make_service()
    plan = [
        PlannedTask(id="retrieve_context", agent="retriever", title="Retrieve", description="Internal docs."),
        PlannedTask(id="research_current_context", agent="researcher", title="Research", description="Web context."),
        PlannedTask(
            id="write_final",
            agent="writer",
            title="Write",
            description="Final answer.",
            depends_on=["retrieve_context", "research_current_context"],
        ),
    ]
    captured: Dict[str, Any] = {}

    async def fake_plan(**kwargs: Any) -> tuple[List[PlannedTask], str]:
        return plan, "independent retriever and researcher"

    async def fake_execute(
        *,
        task: PlannedTask,
        state: Dict[str, Any],
        top_k: int,
        score_threshold: float | None,
        options: Dict[str, Any],
        use_rag: bool,
    ) -> TaskOutcome:
        if task.agent == "retriever":
            chunk = RetrievedChunk(
                id="doc-1",
                score=0.91,
                text="Internal design document",
                metadata={"path": "docs/design.md"},
            )
            state["retrieval_context"] = "[Document 1] docs/design.md\nInternal design document"
            state["evidence_ids"] = ["doc-1"]
            state["evidence_registry"] = {"doc-1": chunk}
            return TaskOutcome(
                status="completed",
                summary="Collected 1 internal document matches.",
                sources=[chunk],
            )
        if task.agent == "researcher":
            chunk = RetrievedChunk(
                id="https://example.com/fresh",
                score=0.8,
                text="Fresh public excerpt",
                metadata={"path": "https://example.com/fresh", "source": "web"},
            )
            state["web_context"] = "Fresh public context"
            state["evidence_ids"] = list(state.get("evidence_ids") or []) + [chunk.id]
            registry = dict(state.get("evidence_registry") or {})
            registry[chunk.id] = chunk
            state["evidence_registry"] = registry
            return TaskOutcome(
                status="completed",
                summary="Collected 1 fresh web results.",
                sources=[chunk],
            )
        captured["retrieval_context"] = state.get("retrieval_context")
        captured["web_context"] = state.get("web_context")
        captured["evidence_ids"] = list(state.get("evidence_ids") or [])
        state["final_answer"] = "Merged answer."
        return TaskOutcome(status="completed", summary="Produced the final answer.")

    async def fake_plan_and_run() -> None:
        with patch.object(service, "_build_plan", side_effect=fake_plan):
            with patch.object(service, "_execute_task", side_effect=fake_execute):
                await service.run_mode(
                    mode="workflow",
                    query="Cross-check local docs with fresh public context.",
                    system_prompt="You are a principled assistant.",
                    chat_history=[],
                    conversation_id="conversation-merge",
                    user_id="00000000-0000-0000-0000-0000000000dd",
                    top_k=4,
                    score_threshold=None,
                    options={},
                    use_rag=True,
                    include_trace=True,
                    persist_memory=False,
                    max_steps=6,
                )

    asyncio.run(fake_plan_and_run())

    assert captured["retrieval_context"]
    assert captured["web_context"]
    assert captured["evidence_ids"] == ["doc-1", "https://example.com/fresh"]
