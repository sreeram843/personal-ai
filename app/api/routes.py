from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import get_settings, Settings
from app.core.deps import (
    get_job_store,
    get_live_data_manager,
    get_llm_gateway,
    get_object_storage,
    get_ollama_client,
    get_run_store,
    get_tool_registry,
    get_vector_store,
    get_web_search,
    get_workflow_model_profile,
    get_workflow_memory_store,
)
from app.db.models import Conversation
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage, RetrievedChunk
from app.schemas.content_block import ContentBlock
from app.schemas.documents import IngestRequest, IngestResponse
from app.schemas.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from app.schemas.run import RunStatus, WorkflowRun
from app.services.chat_execution import execute_chat_mode, execute_chat_mode_stream
from app.services.usage_meter import set_usage_context
from app.services.live_data_manager import LiveDataManager
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.llamaindex_rag import query_with_llamaindex
from app.services.orchestrated_chat import OrchestratedChatService
from app.services.ollama import OllamaClient
from app.services.run_store import RunStore
from app.services.vector_store import VectorStore
from app.services.workflow_memory import WorkflowMemoryStore
from app.services.information_routing import (
    is_corpus_overview_query,
    is_document_grounded_query,
    is_quick_social_utterance,
    should_route_smart_toward_workflow,
)
from app.services.health import readiness_report
from app.services.system_prompt import get_system_prompt
from app.services.web_search import WebSearchService
from app.services.chat_persistence import run_persisted_chat, wrap_chat_stream_with_persistence
from app.services.ingest_service import (
    ingest_documents_for_user,
    should_enqueue_ingest,
)
from app.services.ingest_validation import validate_ingest_documents
from app.services.object_storage import ObjectStorage
from app.services.chat_messages import get_last_user_message
from app.services.orchestrated_runner import (
    build_orchestrated_service,
    merge_workflow_options,
    run_orchestrated_mode,
)
from app.services.task_queue import TaskQueue, get_task_queue
from app.services.tool_registry import ToolRegistry
from app.services.workflow_run_access import require_workflow_run, verify_conversation_owned_by_user

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateWorkflowRunRequest(BaseModel):
    mode: Literal["chat", "rag", "workflow"] = "workflow"
    conversation_id: Optional[str] = None
    run_id: Optional[str] = None

RAG_CITATION_RULE = "Use [path] or [title p.X]; if unsure, say 'I cannot verify this.'"


def _format_chat_response(message: str) -> str:
    """Return plain assistant text for the client. Strips legacy terminal-style prefixes if present."""
    text = (message or "").strip()
    if not text:
        return "I couldn't generate a response. Please try again."
    if "MACHINE_ALPHA_7: >" in text:
        text = text.split("MACHINE_ALPHA_7: >", 1)[-1].strip()
    if text.startswith(">") and not text.startswith(">>"):
        text = text[1:].strip()
    return text


def _now_readable() -> str:
    """Return a clean UTC timestamp string: 'YYYY-MM-DD HH:MM:SS UTC'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _append_data_as_of(message: str, data_as_of_utc: str) -> str:
    """Append a recency marker for internet-derived answers."""
    marker = f"Data fetched: {data_as_of_utc}"
    if marker in message or f"Fetched: {data_as_of_utc}" in message:
        return message
    return f"{message}\n{marker}"


def _get_last_user_message(payload: ChatRequest) -> ChatMessage:
    return get_last_user_message(payload)


def _merge_workflow_options(payload: ChatRequest) -> Dict[str, Any]:
    return merge_workflow_options(payload)


async def _live_data_short_circuit(
    *,
    payload: ChatRequest,
    live_data: LiveDataManager,
) -> ChatResponse | None:
    last_user_message = _get_last_user_message(payload)
    history = [{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]]
    adapter_result = await live_data.resolve(
        last_user_message.content,
        chat_history=history,
    )
    if adapter_result:
        rendered, ts = live_data.render(adapter_result)
        blocks = LiveDataManager.to_blocks(adapter_result)
        message = (
            LiveDataManager.companion_message(adapter_result)
            if blocks
            else rendered
        )
        return ChatResponse(
            message=_format_chat_response(_append_data_as_of(message, ts)),
            sources=[],
            live=LiveDataManager.to_provenance(adapter_result),
            blocks=blocks,
        )

    # Fail closed only for adapter-specific intents (rates, weather, news, …). If the user
    # only used generic "fresh" wording (e.g. "tomorrow" for a sports match), let smart_chat
    # / workflow answer via web + LLM instead of an error block.
    if live_data.is_live_intent_query(
        last_user_message.content,
    ) and not LiveDataManager.is_only_generic_freshness_live_intent(last_user_message.content):
        unresolved = live_data.unresolved_live_intent_result()
        rendered, ts = live_data.render(unresolved)
        return ChatResponse(
            message=_format_chat_response(_append_data_as_of(rendered, ts)),
            sources=[],
            live=LiveDataManager.to_provenance(unresolved),
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
    return build_orchestrated_service(
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        workflow_memory=workflow_memory,
    )


def _select_smart_mode(payload: ChatRequest) -> Literal["chat", "rag", "workflow"]:
    """Auto-route a user prompt to chat, document RAG, or multi-agent workflow."""
    query = _get_last_user_message(payload).content.strip()
    lowered = query.lower()
    words = query.split()

    if is_quick_social_utterance(query):
        return "chat"

    if is_document_grounded_query(query) or is_corpus_overview_query(query):
        return "rag"

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

    if should_route_smart_toward_workflow(query):
        return "workflow"
    if len(words) >= 24:
        return "workflow"
    if any(term in lowered for term in complex_reasoning_terms):
        return "workflow"

    return "chat"


async def _run_orchestrated_mode(
    *,
    mode: Literal["chat", "rag", "workflow"],
    payload: ChatRequest,
    user_id: str,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    vector_store: VectorStore,
    web_search: WebSearchService,
    workflow_memory: WorkflowMemoryStore,
) -> ChatResponse:
    response = await run_orchestrated_mode(
        mode=mode,
        payload=payload,
        user_id=user_id,
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        vector_store=vector_store,
        web_search=web_search,
        workflow_memory=workflow_memory,
        tool_registry=get_tool_registry(),
    )
    response.message = _format_chat_response(response.message)
    return response


def _encode_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_orchestrated_mode(
    *,
    mode: Literal["chat", "rag", "workflow"] = "workflow",
    payload: ChatRequest,
    user_id: str,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    vector_store: VectorStore,
    web_search: WebSearchService,
    workflow_memory: WorkflowMemoryStore,
    run_store: Optional[RunStore] = None,
    run_id: Optional[str] = None,
) -> AsyncIterator[str]:
    if mode == "chat":
        try:
            async for event in execute_chat_mode_stream(
                payload=payload,
                user_id=user_id,
                ollama=ollama,
                llm_gateway=llm_gateway,
                model_profile=model_profile,
                vector_store=vector_store,
                web_search=web_search,
                workflow_memory=workflow_memory,
                tool_registry=get_tool_registry(),
            ):
                if event.get("type") == "final":
                    response = ChatResponse.model_validate(event["response"])
                    response.message = _format_chat_response(response.message)
                    if run_store and run_id:
                        run_store.update_run_status(run_id, RunStatus.COMPLETED)
                    yield _encode_sse({"type": "final", "response": response.model_dump()})
                else:
                    yield _encode_sse(event)
        except Exception as exc:
            if run_store and run_id:
                run_store.update_run_status(run_id, RunStatus.FAILED, error=str(exc))
            logger.exception("Chat stream failed")
            yield _encode_sse({"type": "error", "message": str(exc)})
        return
    service = _build_orchestrated_service(
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        workflow_memory=workflow_memory,
    )
    workflow = payload.workflow
    settings = get_settings()
    try:
        async for event in service.stream_mode(
            mode=mode,
            query=_get_last_user_message(payload).content,
            system_prompt=get_system_prompt(),
            chat_history=[{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]],
            conversation_id=payload.conversation_id,
            user_id=user_id,
            top_k=payload.top_k or settings.default_top_k,
            score_threshold=payload.score_threshold,
            options=_merge_workflow_options(payload),
            use_rag=workflow.use_rag if workflow else mode != "chat",
            include_trace=workflow.include_trace if workflow else mode == "workflow",
            persist_memory=workflow.persist_memory if workflow else mode == "workflow",
            max_steps=workflow.max_steps if workflow else 6,
        ):
            if event["type"] == "final":
                event["response"]["message"] = _format_chat_response(event["response"]["message"])
                if run_id and event["response"].get("workflow"):
                    event["response"]["workflow"]["run_id"] = run_id
                if run_store and run_id:
                    run_store.update_run_status(run_id, RunStatus.COMPLETED)
            yield _encode_sse(event)
    except Exception as exc:
        if run_store and run_id:
            run_store.update_run_status(run_id, RunStatus.FAILED, error=str(exc))
        logger.exception("Orchestrated stream failed")
        yield _encode_sse({"type": "error", "message": str(exc)})


@router.post("/workflow_runs", response_model=WorkflowRun)
async def create_workflow_run(
    payload: CreateWorkflowRunRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Create a durable workflow run record for inspection/control."""
    verify_conversation_owned_by_user(db, user, payload.conversation_id)
    return run_store.create_run(
        mode=payload.mode,
        conversation_id=payload.conversation_id,
        run_id=payload.run_id,
        user_id=str(user.id),
    )


@router.get("/workflow_runs", response_model=List[WorkflowRun])
async def list_workflow_runs(
    conversation_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    run_store: RunStore = Depends(get_run_store),
) -> List[WorkflowRun]:
    """List workflow runs by conversation ID."""
    verify_conversation_owned_by_user(db, user, conversation_id)
    return run_store.list_runs_by_conversation(conversation_id, user_id=str(user.id))


@router.get("/workflow_runs/{run_id}", response_model=WorkflowRun)
async def get_workflow_run(
    run_id: str,
    user: CurrentUser,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Fetch a single workflow run by run ID."""
    return require_workflow_run(run_store, run_id=run_id, user=user)


@router.post("/workflow_runs/{run_id}/pause", response_model=WorkflowRun)
async def pause_workflow_run(
    run_id: str,
    user: CurrentUser,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Pause an in-flight workflow run."""
    run = require_workflow_run(run_store, run_id=run_id, user=user)
    if run.status not in {RunStatus.IN_PROGRESS, RunStatus.RESUMING}:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not active")
    updated = run_store.update_run_status(run_id, RunStatus.PAUSED, user_id=str(user.id))
    if not updated:
        raise HTTPException(status_code=500, detail=f"Failed to pause run '{run_id}'")
    return updated


@router.post("/workflow_runs/{run_id}/resume", response_model=WorkflowRun)
async def resume_workflow_run(
    run_id: str,
    user: CurrentUser,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Resume a paused workflow run by switching to RESUMING state."""
    run = require_workflow_run(run_store, run_id=run_id, user=user)
    if run.status != RunStatus.PAUSED:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not paused")
    updated = run_store.update_run_status(run_id, RunStatus.RESUMING, user_id=str(user.id))
    if not updated:
        raise HTTPException(status_code=500, detail=f"Failed to resume run '{run_id}'")
    return updated


@router.post("/workflow_runs/{run_id}/cancel", response_model=WorkflowRun)
async def cancel_workflow_run(
    run_id: str,
    user: CurrentUser,
    run_store: RunStore = Depends(get_run_store),
) -> WorkflowRun:
    """Cancel a workflow run unless it is already terminal."""
    run = require_workflow_run(run_store, run_id=run_id, user=user)
    if run.status in {RunStatus.COMPLETED, RunStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is already terminal")
    updated = run_store.update_run_status(run_id, RunStatus.CANCELLED, user_id=str(user.id))
    if not updated:
        raise HTTPException(status_code=500, detail=f"Failed to cancel run '{run_id}'")
    return updated


@router.get("/health")
async def health() -> dict:
    """Liveness probe — process is up."""
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name}


@router.get("/ready")
async def ready() -> dict:
    """Readiness probe — critical dependencies are reachable."""
    settings = get_settings()
    report = await readiness_report(settings=settings)
    if report["status"] != "ready":
        raise HTTPException(status_code=503, detail=report)
    return report


@router.get("/live/blocks/refresh", response_model=ContentBlock)
async def refresh_live_block(
    key: str,
    user: CurrentUser,
    live_data: LiveDataManager = Depends(get_live_data_manager),
) -> ContentBlock:
    """Poll updated data for a live card subscription (sports scores, live stocks)."""
    block = await live_data.refresh_block(key)
    if block is None:
        raise HTTPException(status_code=404, detail="Live block not found or not refreshable")
    return block


@router.get("/tools")
async def list_tools(
    role: str = "chat_agent",
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> dict:
    """List tools available to a role (for UI connector panels and debugging)."""
    tools = tool_registry.list_tools_for_role(role)
    return {
        "role": role,
        "tools": [
            {
                "tool_id": spec.tool_id,
                "name": spec.name,
                "description": spec.description,
                "risk_class": spec.risk_class.value,
                "requires_approval": spec.requires_approval,
            }
            for spec in tools.values()
        ],
    }


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    payload: IngestRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    vector_store: VectorStore = Depends(get_vector_store),
    object_storage: ObjectStorage = Depends(get_object_storage),
    job_store: JobStore = Depends(get_job_store),
    task_queue: TaskQueue = Depends(get_task_queue),
) -> IngestResponse:
    """Embed and store documents inside Qdrant for the authenticated user."""

    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    validate_ingest_documents(settings, payload.documents)

    if should_enqueue_ingest(settings, payload.documents):
        job = job_store.create_job(kind=BackgroundJobKind.INGEST, user_id=str(user.id))
        documents_payload = [doc.model_dump(mode="json") for doc in payload.documents]
        try:
            await task_queue.enqueue_ingest(job=job, documents=documents_payload)
        except Exception as exc:
            job_store.update_job(job.job_id, status=BackgroundJobStatus.FAILED, error=str(exc))
            raise HTTPException(status_code=503, detail=f"Failed to enqueue ingest job: {exc}") from exc
        return IngestResponse(job_id=job.job_id, status=BackgroundJobStatus.QUEUED)

    try:
        count = await ingest_documents_for_user(
            db=db,
            user=user,
            documents=payload.documents,
            settings=settings,
            ollama=ollama,
            vector_store=vector_store,
            object_storage=object_storage,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest error: {exc}") from exc
    return IngestResponse(count=count)


@router.get("/jobs/{job_id}", response_model=BackgroundJob)
async def get_background_job(
    job_id: str,
    user: CurrentUser,
    job_store: JobStore = Depends(get_job_store),
) -> BackgroundJob:
    job = job_store.get_job(job_id)
    if job is None or job.user_id != str(user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
) -> ChatResponse:
    """Direct chat — fast path without smart auto-routing to RAG/workflow."""
    set_usage_context(user_id=user.id, route="chat")

    async def handler(request: ChatRequest, _conversation: Conversation) -> ChatResponse:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            return shortcut
        return await _run_orchestrated_mode(
            mode="chat",
            payload=request,
            user_id=str(user.id),
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
        )

    return await run_persisted_chat(
        db=db,
        user=user,
        payload=payload,
        mode="chat",
        handler=handler,
    )


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
) -> StreamingResponse:
    """Streaming direct chat — fast path without smart auto-routing."""
    set_usage_context(user_id=user.id, route="chat")

    async def stream_factory(request: ChatRequest) -> AsyncIterator[str]:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            yield _encode_sse({"type": "final", "response": shortcut.model_dump()})
            return

        async for event in _stream_orchestrated_mode(
            mode="chat",
            payload=request,
            user_id=str(user.id),
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
        ):
            yield event

    return StreamingResponse(
        wrap_chat_stream_with_persistence(
            db=db,
            user=user,
            payload=payload,
            mode="chat",
            stream_factory=stream_factory,
        ),
        media_type="text/event-stream",
        headers={"X-Chat-Route": "chat"},
    )


@router.post("/rag_chat", response_model=ChatResponse)
async def rag_chat(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
) -> ChatResponse:
    """Answer a RAG request through the shared orchestrated backend path."""
    set_usage_context(user_id=user.id, route="rag")

    async def handler(request: ChatRequest, _conversation: Conversation) -> ChatResponse:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            return shortcut
        return await _run_orchestrated_mode(
            mode="rag",
            payload=request,
            user_id=str(user.id),
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
        )

    return await run_persisted_chat(
        db=db,
        user=user,
        payload=payload,
        mode="rag",
        handler=handler,
    )


@router.post("/workflow_chat", response_model=ChatResponse)
async def workflow_chat(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
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
    set_usage_context(user_id=user.id, route="workflow")

    async def handler(request: ChatRequest, _conversation: Conversation) -> ChatResponse:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            return shortcut

        run = run_store.create_run(mode="workflow", conversation_id=request.conversation_id, user_id=str(user.id))
        run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
        try:
            response = await _run_orchestrated_mode(
                mode="workflow",
                payload=request,
                user_id=str(user.id),
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

    return await run_persisted_chat(
        db=db,
        user=user,
        payload=payload,
        mode="workflow",
        handler=handler,
    )


@router.post("/workflow_chat/stream")
async def workflow_chat_stream(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
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
    set_usage_context(user_id=user.id, route="workflow")

    async def stream_factory(request: ChatRequest) -> AsyncIterator[str]:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            yield _encode_sse({"type": "final", "response": shortcut.model_dump()})
            return

        run = run_store.create_run(mode="workflow", conversation_id=request.conversation_id, user_id=str(user.id))
        run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
        async for event in _stream_orchestrated_mode(
            mode="workflow",
            payload=request,
            user_id=str(user.id),
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
            run_store=run_store,
            run_id=run.run_id,
        ):
            yield event

    return StreamingResponse(
        wrap_chat_stream_with_persistence(
            db=db,
            user=user,
            payload=payload,
            mode="workflow",
            stream_factory=stream_factory,
        ),
        media_type="text/event-stream",
    )


@router.post("/workflow_chat/background", response_model=WorkflowRun)
async def workflow_chat_background(
    payload: ChatRequest,
    user: CurrentUser,
    run_store: RunStore = Depends(get_run_store),
    job_store: JobStore = Depends(get_job_store),
    task_queue: TaskQueue = Depends(get_task_queue),
) -> WorkflowRun:
    """Queue a long workflow run for background execution."""
    settings = get_settings()
    if not settings.enable_background_workers:
        raise HTTPException(status_code=400, detail="Background workers are not enabled")

    run = run_store.create_run(mode="workflow", conversation_id=payload.conversation_id, user_id=str(user.id))
    job = job_store.create_job(
        kind=BackgroundJobKind.WORKFLOW,
        user_id=str(user.id),
        run_id=run.run_id,
    )
    try:
        await task_queue.enqueue_workflow(
            run_id=run.run_id,
            user_id=str(user.id),
            payload=payload.model_dump(mode="json"),
            job=job,
        )
    except Exception as exc:
        job_store.update_job(job.job_id, status=BackgroundJobStatus.FAILED, error=str(exc))
        run_store.update_run_status(run.run_id, RunStatus.FAILED, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Failed to enqueue workflow job: {exc}") from exc
    return run


@router.post("/smart_chat", response_model=ChatResponse)
async def smart_chat(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
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
    set_usage_context(user_id=user.id, route="smart")

    async def handler(request: ChatRequest, _conversation: Conversation) -> ChatResponse:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            return shortcut

        selected_mode = _select_smart_mode(request)
        run = run_store.create_run(
            mode=selected_mode,
            conversation_id=request.conversation_id,
            user_id=str(user.id),
        )
        run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
        try:
            response = await _run_orchestrated_mode(
                mode=selected_mode,
                payload=request,
                user_id=str(user.id),
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

    return await run_persisted_chat(
        db=db,
        user=user,
        payload=payload,
        mode="smart",
        handler=handler,
    )


@router.post("/smart_chat/stream")
async def smart_chat_stream(
    payload: ChatRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
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
    set_usage_context(user_id=user.id, route="smart")

    selected_mode = _select_smart_mode(payload)

    async def stream_factory(request: ChatRequest) -> AsyncIterator[str]:
        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            yield _encode_sse({"type": "final", "response": shortcut.model_dump()})
            return

        mode = _select_smart_mode(request)
        run = run_store.create_run(mode=mode, conversation_id=request.conversation_id, user_id=str(user.id))
        run_store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
        async for event in _stream_orchestrated_mode(
            mode=mode,
            payload=request,
            user_id=str(user.id),
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
            run_store=run_store,
            run_id=run.run_id,
        ):
            yield event

    return StreamingResponse(
        wrap_chat_stream_with_persistence(
            db=db,
            user=user,
            payload=payload,
            mode=selected_mode,
            stream_factory=stream_factory,
        ),
        media_type="text/event-stream",
        headers={"X-Chat-Route": selected_mode},
    )


__all__ = ["router"]
