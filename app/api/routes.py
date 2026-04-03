from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import (
    get_live_data_manager,
    get_llm_gateway,
    get_ollama_client,
    get_run_store,
    get_vector_store,
    get_web_search,
    get_workflow_model_profile,
    get_workflow_memory_store,
)
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage, RetrievedChunk
from app.schemas.documents import IngestRequest, IngestResponse
from app.schemas.run import RunStatus, WorkflowRun
from app.services.langchain_agent import run_langchain_agent
from app.services.live_data_manager import LiveDataManager
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.llamaindex_rag import ingest_documents_with_llamaindex, query_with_llamaindex
from app.services.orchestrated_chat import OrchestratedChatService
from app.services.ollama import OllamaClient
from app.services.run_store import RunStore
from app.services.vector_store import StoredDocument, VectorStore
from app.services.workflow_memory import WorkflowMemoryStore
from app.services.web_search import (
    WebSearchService,
    should_prioritize_fresh_web_data,
)

router = APIRouter()


class CreateWorkflowRunRequest(BaseModel):
    mode: Literal["chat", "rag", "workflow"] = "workflow"
    conversation_id: Optional[str] = None
    run_id: Optional[str] = None

RAG_CITATION_RULE = "Use [path] or [title p.X]; if unsure, say 'I cannot verify this.'"
SYSTEM_PROMPT = """
You are a principled, user-centric assistant. Your purpose is to help people solve problems efficiently \
through clear thinking and reliable action.

## Core Traits (Non-Negotiable)

**1. Intuitive**
- Use clear, common vocabulary. Define technical terms when necessary.
- Structure for easy scanning: headings, short paragraphs, bullets.
- Don't try to be everything. Delegate when another tool or person is better.
- When you can't solve it, say so and suggest alternatives.

**2. Coachable and Eager to Learn**
- Accept correction gracefully. Adjust your approach based on feedback.
- Remember context. Refer back to earlier points in the conversation.
- Ask clarifying questions when instructions are ambiguous.
- Be explicit about what you've learned from the user.

**3. Contextually Smart**
- Read between the lines. A question about "time management" might signal feeling overwhelmed.
- Track stated constraints (budget, timeline, audience) and refer to them.
- Notice when the user is building on earlier work vs. starting fresh.
- Infer intent from phrasing, tone, and what's left unsaid.

**4. An Effective Communicator**
- Match verbosity to the task. Brief for routine, detailed for complex.
- Lead with the answer; explain reasoning second.
- Avoid repetition. Refer back to earlier points instead.
- Know when silence is better than reassurance.

**5. Reliable**
- Acknowledge processing delays upfront: "This may take 30 seconds..."
- Report successes clearly: "Done. Here's what changed."
- Communicate failures honestly: "I couldn't verify [X]. Here's why..."
- Don't speculate about live data. Say "I can't confirm that" instead.

**6. Well-Connected**
- Know your limits. Name them explicitly.
- When a task is outside your scope, offer a specific alternative.
- Suggest integrations or next steps that multiply the user's options.
- Be respectful when inviting outside help.

**7. Secure**
- Never assume authorization before sensitive operations.
- Don't speculate about credentials or private data. Refuse requests that require them.
- Be transparent about what you can and cannot see.
- When in doubt about a request's safety, decline and explain why.

## Policy

- Use your best judgment. These seven traits work together; don't optimize for one at another's expense.
- When in doubt, prioritize honesty and clarity over helpfulness.
- Each conversation is independent unless the user explicitly references earlier ones.
""".strip()


def _to_machine_alpha_7_output(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        cleaned = "ERROR 500: EMPTY RESPONSE PAYLOAD"
    if cleaned.startswith("[") and "MACHINE_ALPHA_7: >" in cleaned:
        return cleaned

    if "MACHINE_ALPHA_7: >" in cleaned:
        cleaned = cleaned.split("MACHINE_ALPHA_7: >", 1)[1].strip()

    if cleaned.startswith(">"):
        cleaned = cleaned[1:].strip()

    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] MACHINE_ALPHA_7: > {cleaned}"


def _now_readable() -> str:
    """Return a clean UTC timestamp string: 'YYYY-MM-DD HH:MM:SS UTC'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _append_data_as_of(message: str, data_as_of_utc: str) -> str:
    """Append a recency marker for internet-derived answers."""
    marker = f"Data fetched: {data_as_of_utc}"
    if marker in message:
        return message
    return f"{message}\n{marker}"


def _get_last_user_message(payload: ChatRequest) -> ChatMessage:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="Missing chat messages")

    last_user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if last_user_message is None:
        raise HTTPException(status_code=400, detail="At least one user message is required")
    return last_user_message


async def _live_data_short_circuit(
    *,
    payload: ChatRequest,
    live_data: LiveDataManager,
) -> ChatResponse | None:
    last_user_message = _get_last_user_message(payload)
    adapter_result = await live_data.resolve(last_user_message.content)
    if adapter_result:
        rendered, ts = live_data.render(adapter_result)
        return ChatResponse(
            message=_to_machine_alpha_7_output(_append_data_as_of(rendered, ts)),
            sources=[],
        )

    if live_data.is_live_intent_query(last_user_message.content):
        unresolved = live_data.unresolved_live_intent_result()
        rendered, ts = live_data.render(unresolved)
        return ChatResponse(
            message=_to_machine_alpha_7_output(_append_data_as_of(rendered, ts)),
            sources=[],
        )

    return None


def _build_orchestrated_service(
    *,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    web_search: WebSearchService,
    vector_store: VectorStore,
    workflow_memory: WorkflowMemoryStore,
) -> OrchestratedChatService:
    return OrchestratedChatService(
        embed_client=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        memory_store=workflow_memory,
    )


def _select_smart_mode(payload: ChatRequest) -> Literal["chat", "rag", "workflow"]:
    query = _get_last_user_message(payload).content.strip()
    lowered = query.lower()
    words = query.split()

    quick_only_terms = {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "yo",
    }
    if len(words) <= 4 and lowered in quick_only_terms:
        return "chat"

    complex_reasoning_terms = (
        "compare",
        "trade-off",
        "tradeoff",
        "analyze",
        "analysis",
        "roadmap",
        "strategy",
        "multi-step",
        "step by step",
        "cross-check",
        "synthesize",
        "audit",
        "review",
        "plan",
        "workflow",
    )

    if should_prioritize_fresh_web_data(query):
        return "workflow"
    if len(words) >= 24:
        return "workflow"
    if any(term in lowered for term in complex_reasoning_terms):
        return "workflow"

    return "rag"


async def _run_orchestrated_mode(
    *,
    mode: Literal["chat", "rag", "workflow"],
    payload: ChatRequest,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    vector_store: VectorStore,
    web_search: WebSearchService,
    workflow_memory: WorkflowMemoryStore,
) -> ChatResponse:
    settings = get_settings()
    service = _build_orchestrated_service(
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        workflow_memory=workflow_memory,
    )
    workflow = payload.workflow
    response = await service.run_mode(
        mode=mode,
        query=_get_last_user_message(payload).content,
        system_prompt=SYSTEM_PROMPT,
        chat_history=[{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]],
        conversation_id=payload.conversation_id,
        top_k=payload.top_k or settings.default_top_k,
        score_threshold=payload.score_threshold,
        options=_merge_workflow_options(payload),
        use_rag=workflow.use_rag if workflow else mode != "chat",
        include_trace=workflow.include_trace if workflow else mode == "workflow",
        persist_memory=workflow.persist_memory if workflow else mode == "workflow",
        max_steps=workflow.max_steps if workflow else 6,
    )
    response.message = _to_machine_alpha_7_output(response.message)
    return response


def _encode_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
    
def _merge_workflow_options(payload: ChatRequest) -> Dict[str, Any]:
    merged = dict(payload.options or {})
    workflow = payload.workflow
    if not workflow:
        return merged
    merged.setdefault("reviewer_quorum", workflow.reviewer_quorum)
    merged.setdefault("require_evidence_markers", workflow.require_evidence_markers)
    merged.setdefault("trust_lanes_enabled", workflow.trust_lanes_enabled)
    merged.setdefault("token_budget", workflow.token_budget)
    merged.setdefault("progressive_disclosure_level", workflow.progressive_disclosure_level)
    return merged


async def _stream_orchestrated_mode(
    *,
    mode: Literal["chat", "rag", "workflow"] = "workflow",
    payload: ChatRequest,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    vector_store: VectorStore,
    web_search: WebSearchService,
    workflow_memory: WorkflowMemoryStore,
    run_store: Optional[RunStore] = None,
    run_id: Optional[str] = None,
) -> AsyncIterator[str]:
    service = _build_orchestrated_service(
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        workflow_memory=workflow_memory,
    )
    settings = get_settings()
    workflow = payload.workflow
    try:
        async for event in service.stream_mode(
            mode=mode,
            query=_get_last_user_message(payload).content,
            system_prompt=SYSTEM_PROMPT,
            chat_history=[{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]],
            conversation_id=payload.conversation_id,
            top_k=payload.top_k or settings.default_top_k,
            score_threshold=payload.score_threshold,
            options=_merge_workflow_options(payload),
            use_rag=workflow.use_rag if workflow else mode != "chat",
            include_trace=workflow.include_trace if workflow else mode == "workflow",
            persist_memory=workflow.persist_memory if workflow else mode == "workflow",
            max_steps=workflow.max_steps if workflow else 6,
        ):
            if event["type"] == "final":
                event["response"]["message"] = _to_machine_alpha_7_output(event["response"]["message"])
                if run_id and event["response"].get("workflow"):
                    event["response"]["workflow"]["run_id"] = run_id
                if run_store and run_id:
                    run_store.update_run_status(run_id, RunStatus.COMPLETED)
            yield _encode_sse(event)
    except Exception as exc:
        if run_store and run_id:
            run_store.update_run_status(run_id, RunStatus.FAILED, error=str(exc))
        raise


@router.post("/workflow_runs", response_model=WorkflowRun)
async def create_workflow_run(
    payload: CreateWorkflowRunRequest,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Create a durable workflow run record for inspection/control."""
    return run_store.create_run(mode=payload.mode, conversation_id=payload.conversation_id, run_id=payload.run_id)


@router.get("/workflow_runs", response_model=List[WorkflowRun])
async def list_workflow_runs(
    conversation_id: str,
    run_store: RunStore = Depends(get_run_store),
) -> List[WorkflowRun]:
    """List workflow runs by conversation ID."""
    return run_store.list_runs_by_conversation(conversation_id)


@router.get("/workflow_runs/{run_id}", response_model=WorkflowRun)
async def get_workflow_run(
    run_id: str,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Fetch a single workflow run by run ID."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@router.post("/workflow_runs/{run_id}/pause", response_model=WorkflowRun)
async def pause_workflow_run(
    run_id: str,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Pause an in-flight workflow run."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if run.status not in {RunStatus.IN_PROGRESS, RunStatus.RESUMING}:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not active")
    updated = run_store.update_run_status(run_id, RunStatus.PAUSED)
    if not updated:
        raise HTTPException(status_code=500, detail=f"Failed to pause run '{run_id}'")
    return updated


@router.post("/workflow_runs/{run_id}/resume", response_model=WorkflowRun)
async def resume_workflow_run(
    run_id: str,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Resume a paused workflow run by switching to RESUMING state."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if run.status != RunStatus.PAUSED:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not paused")
    updated = run_store.update_run_status(run_id, RunStatus.RESUMING)
    if not updated:
        raise HTTPException(status_code=500, detail=f"Failed to resume run '{run_id}'")
    return updated


@router.post("/workflow_runs/{run_id}/cancel", response_model=WorkflowRun)
async def cancel_workflow_run(
    run_id: str,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Cancel a workflow run unless it is already terminal."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if run.status in {RunStatus.COMPLETED, RunStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is already terminal")
    updated = run_store.update_run_status(run_id, RunStatus.CANCELLED)
    if not updated:
        raise HTTPException(status_code=500, detail=f"Failed to cancel run '{run_id}'")
    return updated


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    payload: IngestRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> IngestResponse:
    """Embed and store documents inside Qdrant."""

    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    settings = get_settings()
    if settings.enable_llamaindex_rag:
        docs = [
            {
                "text": doc.text,
                "metadata": doc.metadata,
            }
            for doc in payload.documents
        ]
        try:
            count = await run_in_threadpool(ingest_documents_with_llamaindex, settings, docs)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"LlamaIndex ingest error: {exc}",
            )
        return IngestResponse(count=count)

    texts = [doc.text for doc in payload.documents]
    embeddings = await ollama.embed(texts)
    stored_docs = [
        StoredDocument(text=doc.text, metadata=doc.metadata, id=doc.id)
        for doc in payload.documents
    ]
    await run_in_threadpool(vector_store.upsert, embeddings, stored_docs)
    return IngestResponse(count=len(stored_docs))


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
) -> ChatResponse:
    """Answer a chat request through the shared orchestrated backend path."""

    shortcut = await _live_data_short_circuit(payload=payload, live_data=live_data)
    if shortcut:
        return shortcut

    return await _run_orchestrated_mode(
        mode="chat",
        payload=payload,
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        vector_store=vector_store,
        web_search=web_search,
        workflow_memory=workflow_memory,
    )


@router.post("/rag_chat", response_model=ChatResponse)
async def rag_chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
) -> ChatResponse:
    """Answer a RAG request through the shared orchestrated backend path."""

    shortcut = await _live_data_short_circuit(payload=payload, live_data=live_data)
    if shortcut:
        return shortcut

    return await _run_orchestrated_mode(
        mode="rag",
        payload=payload,
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        vector_store=vector_store,
        web_search=web_search,
        workflow_memory=workflow_memory,
    )


@router.post("/workflow_chat", response_model=ChatResponse)
async def workflow_chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
    run_store: RunStore = Depends(get_run_store),
) -> ChatResponse:
    """Answer a request through the shared orchestrated backend path with trace output."""

    shortcut = await _live_data_short_circuit(payload=payload, live_data=live_data)
    if shortcut:
        return shortcut

    run = run_store.create_run(mode="workflow", conversation_id=payload.conversation_id)
    run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
    try:
        response = await _run_orchestrated_mode(
            mode="workflow",
            payload=payload,
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
        )
        if response.workflow:
            response.workflow.run_id = run.run_id
        run_store.update_run_status(run.run_id, RunStatus.COMPLETED)
        return response
    except Exception as exc:
        run_store.update_run_status(run.run_id, RunStatus.FAILED, error=str(exc))
        raise


@router.post("/workflow_chat/stream")
async def workflow_chat_stream(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
    run_store: RunStore = Depends(get_run_store),
) -> StreamingResponse:
    """Stream workflow step progress and final response as SSE."""

    shortcut = await _live_data_short_circuit(payload=payload, live_data=live_data)
    if shortcut:
        async def shortcut_events() -> AsyncIterator[str]:
            yield _encode_sse({"type": "final", "response": shortcut.model_dump()})

        return StreamingResponse(shortcut_events(), media_type="text/event-stream")

    run = run_store.create_run(mode="workflow", conversation_id=payload.conversation_id)
    run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
    return StreamingResponse(
        _stream_orchestrated_mode(
            mode="workflow",
            payload=payload,
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
            run_store=run_store,
            run_id=run.run_id,
        ),
        media_type="text/event-stream",
    )


@router.post("/smart_chat", response_model=ChatResponse)
async def smart_chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
    run_store: RunStore = Depends(get_run_store),
) -> ChatResponse:
    """Smart entrypoint that auto-routes to chat, rag, or workflow."""

    shortcut = await _live_data_short_circuit(payload=payload, live_data=live_data)
    if shortcut:
        return shortcut

    selected_mode = _select_smart_mode(payload)
    run = run_store.create_run(mode=selected_mode, conversation_id=payload.conversation_id)
    run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
    try:
        response = await _run_orchestrated_mode(
            mode=selected_mode,
            payload=payload,
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
        )
        if response.workflow:
            response.workflow.run_id = run.run_id
        run_store.update_run_status(run.run_id, RunStatus.COMPLETED)
        return response
    except Exception as exc:
        run_store.update_run_status(run.run_id, RunStatus.FAILED, error=str(exc))
        raise


@router.post("/smart_chat/stream")
async def smart_chat_stream(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
    run_store: RunStore = Depends(get_run_store),
) -> StreamingResponse:
    """Smart streaming entrypoint with automatic mode selection."""

    shortcut = await _live_data_short_circuit(payload=payload, live_data=live_data)
    if shortcut:
        async def shortcut_events() -> AsyncIterator[str]:
            yield _encode_sse({"type": "final", "response": shortcut.model_dump()})

        return StreamingResponse(shortcut_events(), media_type="text/event-stream")

    selected_mode = _select_smart_mode(payload)
    run = run_store.create_run(mode=selected_mode, conversation_id=payload.conversation_id)
    run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
    return StreamingResponse(
        _stream_orchestrated_mode(
            mode=selected_mode,
            payload=payload,
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
            run_store=run_store,
            run_id=run.run_id,
        ),
        media_type="text/event-stream",
        headers={"X-Smart-Mode": selected_mode},
    )


# Persona Management Endpoints
@router.get("/personas")
async def list_personas() -> dict:
    """List all available personas."""
    from app.services.persona_manager import PersonaManager
    
    manager = PersonaManager()
    personas = manager.list_personas()
    active = manager.get_active_persona()
    
    return {
        "personas": personas,
        "active": active,
    }


@router.post("/personas/switch")
async def switch_persona(request: dict) -> dict:
    """Switch to a different persona."""
    from app.services.persona_manager import PersonaManager
    
    persona_name = request.get("persona")
    if not persona_name:
        raise HTTPException(status_code=400, detail="Missing 'persona' field")
    
    manager = PersonaManager()
    try:
        manager.set_active_persona(persona_name)
        return {
            "status": "switched",
            "active": manager.get_active_persona(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/personas/active")
async def get_active_persona() -> dict:
    """Get the currently active persona."""
    from app.services.persona_manager import PersonaManager
    
    manager = PersonaManager()
    return {
        "active": manager.get_active_persona(),
    }


@router.post("/personas/preview")
async def preview_persona(request: dict) -> dict:
    """Preview a persona's system prompt without switching."""
    from app.services.persona_manager import PersonaManager
    
    persona_name = request.get("persona")
    if not persona_name:
        raise HTTPException(status_code=400, detail="Missing 'persona' field")
    
    manager = PersonaManager()
    try:
        prompt = manager.get_persona_system_prompt(persona_name)
        return {
            "persona": persona_name,
            "system_prompt": prompt,
            "length": len(prompt),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


__all__ = ["router"]
