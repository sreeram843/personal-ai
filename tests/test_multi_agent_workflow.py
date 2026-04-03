from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from app.core.deps import (
    get_live_data_manager,
    get_llm_gateway,
    get_ollama_client,
    get_vector_store,
    get_web_search,
    get_workflow_model_profile,
    get_workflow_memory_store,
)
from app.main import create_app
from app.services.llm_gateway import StageModelConfig, WorkflowModelProfile
from app.services.orchestrated_chat import OrchestratedChatService


class _StubGateway:
    def __init__(self) -> None:
        self.calls = 0
        self.providers = []
        self.models = []

    async def generate(self, *, messages, model: str, options, provider=None):
        self.calls += 1
        self.providers.append(provider)
        self.models.append(model)
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "You are the coordinator." in system_text:
            return "not valid json"
        if "You are the synthesizer." in system_text:
            return "Draft answer using shared evidence."
        if "You are the reviewer." in system_text:
            return "Tighten one sentence and keep citations explicit."
        if "You are the writer." in system_text:
            return "Final coordinated answer."
        return "Fallback answer."


class _ValidPlanGateway(_StubGateway):
    async def generate(self, *, messages, model: str, options, provider=None):
        self.calls += 1
        self.providers.append(provider)
        self.models.append(model)
        system_text = "\n".join(item["content"] for item in messages if item["role"] == "system")
        if "plan verifier" in system_text:
            return json.dumps(
                [
                    {
                        "id": "draft_answer",
                        "agent": "synthesizer",
                        "title": "Draft answer",
                        "description": "Create draft",
                        "depends_on": [],
                    },
                    {
                        "id": "write_final",
                        "agent": "writer",
                        "title": "Write final",
                        "description": "Finalize answer",
                        "depends_on": ["draft_answer"],
                    },
                ]
            )
        if "You are the coordinator." in system_text:
            return json.dumps(
                [
                    {
                        "id": "retrieve_context",
                        "agent": "retriever",
                        "title": "Retrieve",
                        "description": "Retrieve context",
                        "depends_on": [],
                    },
                    {
                        "id": "draft_answer",
                        "agent": "synthesizer",
                        "title": "Draft",
                        "description": "Draft answer",
                        "depends_on": ["retrieve_context"],
                    },
                    {
                        "id": "write_final",
                        "agent": "writer",
                        "title": "Final",
                        "description": "Write final answer",
                        "depends_on": ["draft_answer"],
                    },
                ]
            )
        return await super().generate(messages=messages, model=model, options=options, provider=provider)


def _stub_model_profile() -> WorkflowModelProfile:
    stage = StageModelConfig(provider="ollama", model="test-model")
    return WorkflowModelProfile(
        planner=stage,
        synthesizer=stage,
        reviewer=stage,
        writer=stage,
    )


def _mixed_provider_model_profile() -> WorkflowModelProfile:
    return WorkflowModelProfile(
        planner=StageModelConfig(provider="openai", model="planner-mini"),
        synthesizer=StageModelConfig(provider="ollama", model="synth-fast"),
        reviewer=StageModelConfig(provider="openai", model="review-mini"),
        writer=StageModelConfig(provider="ollama", model="writer-strong"),
    )


class _StubOllama:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class _SearchResult:
    def __init__(self, result_id: str, score: float, payload: dict):
        self.id = result_id
        self.score = score
        self.payload = payload


class _StubVectorStore:
    def search(self, vector, limit=4, score_threshold=None):
        return [
            _SearchResult(
                "doc-1",
                0.91,
                {
                    "text": "Internal design document",
                    "path": "docs/design.md",
                    "name": "Design Doc",
                },
            )
        ]


class _StubWebSearch:
    async def search_with_page_excerpts(self, query: str):
        return [
            {
                "title": "Fresh result",
                "body": "Fresh public context",
                "href": "https://example.com/fresh",
                "excerpt": "Fresh public excerpt",
                "fetched_at_utc": "2026-04-01T00:00:00Z",
            }
        ]


class _StubWorkflowMemoryStore:
    def __init__(self) -> None:
        self.entries = []

    async def get_summary(self, conversation_id: str, limit: int = 6) -> str:
        if self.entries:
            return '## Prior Workflow Memory\n- writer / Final answer: Previous summary'
        return ''

    async def append_entries(self, conversation_id: str, entries):
        self.entries.extend(entries)


class _StubLiveDataManager:
    async def resolve(self, content: str):
        return None

    def is_live_intent_query(self, content: str) -> bool:
        return False

    def unresolved_live_intent_result(self):
        return None

    def render(self, result):
        return "", ""


class _StubResolvedLiveDataManager(_StubLiveDataManager):
    async def resolve(self, content: str):
        return {"status": "ok"}

    def render(self, result):
        return "LIVE RESULT", "2026-04-01 00:00:00 UTC"


def test_multi_agent_workflow_executes_fallback_plan() -> None:
    memory_store = _StubWorkflowMemoryStore()
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=_StubGateway(),
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=memory_store,
    )

    result = asyncio.run(
        service.run_mode(
            mode='workflow',
            query="Summarize the current status of the architecture and cross-check it with local docs.",
            system_prompt="You are a principled assistant.",
            chat_history=[],
            conversation_id='conversation-1',
            top_k=4,
            score_threshold=None,
            options={},
            use_rag=True,
            include_trace=True,
            persist_memory=True,
            max_steps=6,
        )
    )

    assert result.message == "Final coordinated answer."
    assert result.workflow is not None
    assert result.workflow.status in {"completed", "partial"}
    assert result.workflow.steps[0].agent == "coordinator"
    assert any(step.agent == "retriever" for step in result.workflow.steps)
    assert any(step.agent == "writer" for step in result.workflow.steps)
    assert len(result.sources) == 2
    assert memory_store.entries


def test_multi_agent_workflow_skips_retrieval_when_disabled() -> None:
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=_StubGateway(),
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )

    result = asyncio.run(
        service.run_mode(
            mode='chat',
            query="Explain the current architecture.",
            system_prompt="You are a principled assistant.",
            chat_history=[],
            conversation_id='conversation-2',
            top_k=4,
            score_threshold=None,
            options={},
            use_rag=False,
            include_trace=True,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert result.message == "Final coordinated answer."
    assert result.workflow is not None
    retriever_steps = [step for step in result.workflow.steps if step.agent == "retriever"]
    assert retriever_steps == []


def test_workflow_chat_endpoint_returns_trace() -> None:
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_llm_gateway] = lambda: _StubGateway()
    app.dependency_overrides[get_workflow_model_profile] = _stub_model_profile
    app.dependency_overrides[get_vector_store] = lambda: _StubVectorStore()
    app.dependency_overrides[get_web_search] = lambda: _StubWebSearch()
    app.dependency_overrides[get_live_data_manager] = lambda: _StubLiveDataManager()
    app.dependency_overrides[get_workflow_memory_store] = lambda: _StubWorkflowMemoryStore()

    client = TestClient(app)
    response = client.post(
        "/workflow_chat",
        json={
            "conversation_id": "conversation-3",
            "messages": [{"role": "user", "content": "Cross-check the architecture with local docs and fresh context."}],
            "workflow": {
                "enabled": True,
                "use_rag": True,
                "include_trace": True,
                "persist_memory": True,
                "max_steps": 6,
            },
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "MACHINE_ALPHA_7" in payload["message"]
    assert len(payload["sources"]) == 2
    assert payload["workflow"]["mode"] == "multi_agent"
    assert any(step["agent"] == "writer" for step in payload["workflow"]["steps"])


def test_workflow_chat_endpoint_short_circuits_live_data() -> None:
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_llm_gateway] = lambda: _StubGateway()
    app.dependency_overrides[get_workflow_model_profile] = _stub_model_profile
    app.dependency_overrides[get_vector_store] = lambda: _StubVectorStore()
    app.dependency_overrides[get_web_search] = lambda: _StubWebSearch()
    app.dependency_overrides[get_live_data_manager] = lambda: _StubResolvedLiveDataManager()
    app.dependency_overrides[get_workflow_memory_store] = lambda: _StubWorkflowMemoryStore()

    client = TestClient(app)
    response = client.post(
        "/workflow_chat",
        json={"messages": [{"role": "user", "content": "usd to inr"}], "workflow": {"enabled": True}},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "LIVE RESULT" in payload["message"]
    assert payload["workflow"] is None


def test_workflow_stream_endpoint_emits_progress_and_final() -> None:
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_llm_gateway] = lambda: _StubGateway()
    app.dependency_overrides[get_workflow_model_profile] = _stub_model_profile
    app.dependency_overrides[get_vector_store] = lambda: _StubVectorStore()
    app.dependency_overrides[get_web_search] = lambda: _StubWebSearch()
    app.dependency_overrides[get_live_data_manager] = lambda: _StubLiveDataManager()
    app.dependency_overrides[get_workflow_memory_store] = lambda: _StubWorkflowMemoryStore()

    client = TestClient(app)
    response = client.post(
        "/workflow_chat/stream",
        json={
            "conversation_id": "conversation-4",
            "messages": [{"role": "user", "content": "Review the architecture with workflow trace."}],
            "workflow": {"enabled": True, "include_trace": True, "persist_memory": True},
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    frames = [chunk for chunk in response.text.split('\n\n') if chunk.strip()]
    payloads = [json.loads(frame.split('data: ', 1)[1]) for frame in frames if 'data: ' in frame]
    assert any(item['type'] == 'workflow' for item in payloads)
    final_payload = next(item for item in payloads if item['type'] == 'final')
    assert 'MACHINE_ALPHA_7' in final_payload['response']['message']


def test_smart_chat_endpoint_auto_routes_with_trace() -> None:
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_llm_gateway] = lambda: _StubGateway()
    app.dependency_overrides[get_workflow_model_profile] = _stub_model_profile
    app.dependency_overrides[get_vector_store] = lambda: _StubVectorStore()
    app.dependency_overrides[get_web_search] = lambda: _StubWebSearch()
    app.dependency_overrides[get_live_data_manager] = lambda: _StubLiveDataManager()
    app.dependency_overrides[get_workflow_memory_store] = lambda: _StubWorkflowMemoryStore()

    client = TestClient(app)
    response = client.post(
        "/smart_chat",
        json={
            "conversation_id": "conversation-smart-1",
            "messages": [{"role": "user", "content": "Analyze trade-offs and build a roadmap with current context."}],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "MACHINE_ALPHA_7" in payload["message"]
    assert payload["workflow"] is not None
    assert any(step["agent"] == "writer" for step in payload["workflow"]["steps"])


def test_smart_chat_stream_sets_selected_mode_header() -> None:
    app = create_app()
    app.dependency_overrides[get_ollama_client] = lambda: _StubOllama()
    app.dependency_overrides[get_llm_gateway] = lambda: _StubGateway()
    app.dependency_overrides[get_workflow_model_profile] = _stub_model_profile
    app.dependency_overrides[get_vector_store] = lambda: _StubVectorStore()
    app.dependency_overrides[get_web_search] = lambda: _StubWebSearch()
    app.dependency_overrides[get_live_data_manager] = lambda: _StubLiveDataManager()
    app.dependency_overrides[get_workflow_memory_store] = lambda: _StubWorkflowMemoryStore()

    client = TestClient(app)
    response = client.post(
        "/smart_chat/stream",
        json={
            "conversation_id": "conversation-smart-2",
            "messages": [{"role": "user", "content": "Please compare options and draft a strategy."}],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["x-smart-mode"] == "workflow"
    assert response.headers['content-type'].startswith('text/event-stream')


def test_multi_agent_workflow_uses_stage_provider_routing() -> None:
    gateway = _StubGateway()
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=gateway,
        model_profile=_mixed_provider_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )

    result = asyncio.run(
        service.run_mode(
            mode='workflow',
            query="Route different workflow stages to different providers.",
            system_prompt="You are a principled assistant.",
            chat_history=[],
            conversation_id='conversation-5',
            top_k=4,
            score_threshold=None,
            options={},
            use_rag=True,
            include_trace=True,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert result.message == "Final coordinated answer."
    assert gateway.providers == ["openai", "ollama", "openai", "openai", "ollama"]
    assert gateway.models == ["planner-mini", "synth-fast", "review-mini", "review-mini", "writer-strong"]


def test_dual_phase_planner_runs_verifier_pass() -> None:
    gateway = _ValidPlanGateway()
    service = OrchestratedChatService(
        embed_client=_StubOllama(),
        llm_gateway=gateway,
        model_profile=_stub_model_profile(),
        web_search=_StubWebSearch(),
        vector_store=_StubVectorStore(),
        memory_store=_StubWorkflowMemoryStore(),
    )

    result = asyncio.run(
        service.run_mode(
            mode='workflow',
            query="Use a validated plan.",
            system_prompt="You are a principled assistant.",
            chat_history=[],
            conversation_id='conversation-6',
            top_k=4,
            score_threshold=None,
            options={"reviewer_quorum": 1},
            use_rag=True,
            include_trace=True,
            persist_memory=False,
            max_steps=6,
        )
    )

    assert result.workflow is not None
    assert any(step.summary and "verifier" in step.summary.lower() for step in result.workflow.steps)
    assert gateway.calls >= 4