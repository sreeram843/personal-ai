"""OpenAI-compatible /v1 endpoints."""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import (
    get_live_data_manager,
    get_llm_gateway,
    get_ollama_client,
    get_tool_registry,
    get_vector_store,
    get_web_search,
    get_workflow_memory_store,
    get_workflow_model_profile,
)
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_persistence import run_persisted_chat, wrap_chat_stream_with_persistence
from app.services.live_data_manager import LiveDataManager
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.ollama import OllamaClient
from app.services.openai_compat import (
    chat_request_from_openai,
    list_openai_models,
    openai_completion_from_response,
    stream_openai_chunks_from_sse,
)
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.workflow_memory import WorkflowMemoryStore

router = APIRouter(prefix="/v1", tags=["openai"])


def _ensure_enabled(settings: Settings = Depends(get_settings)) -> Settings:
    if not settings.enable_openai_api:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OpenAI-compatible API is disabled")
    return settings


@router.get("/models")
async def list_models(
    user: CurrentUser,
    settings: Settings = Depends(_ensure_enabled),
) -> dict:
    _ = user
    return list_openai_models(settings)


@router.post("/chat/completions")
async def chat_completions(
    body: dict,
    user: CurrentUser,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_ensure_enabled),
    ollama: OllamaClient = Depends(get_ollama_client),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    model_profile: WorkflowModelProfile = Depends(get_workflow_model_profile),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    workflow_memory: WorkflowMemoryStore = Depends(get_workflow_memory_store),
):
    try:
        payload = chat_request_from_openai(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    model = str(body.get("model") or "curai-default")
    stream = bool(body.get("stream"))

    async def handler(request: ChatRequest, _conversation) -> ChatResponse:
        from app.api.routes import _live_data_short_circuit, _run_orchestrated_mode

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

    if not stream:
        response = await run_persisted_chat(
            db=db,
            user=user,
            payload=payload,
            mode="chat",
            handler=handler,
        )
        return openai_completion_from_response(response=response, model=model)

    async def stream_factory(request: ChatRequest) -> AsyncIterator[str]:
        from app.api.routes import _encode_sse, _live_data_short_circuit
        from app.services.chat_execution import execute_chat_mode_stream

        shortcut = await _live_data_short_circuit(payload=request, live_data=live_data)
        if shortcut:
            yield _encode_sse({"type": "final", "response": shortcut.model_dump()})
            return
        async for event in execute_chat_mode_stream(
            payload=request,
            user_id=str(user.id),
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
            tool_registry=get_tool_registry(),
        ):
            yield _encode_sse(event)

    async def openai_stream() -> AsyncIterator[str]:
        sse = wrap_chat_stream_with_persistence(
            db=db,
            user=user,
            payload=payload,
            mode="chat",
            stream_factory=stream_factory,
        )
        async for chunk in stream_openai_chunks_from_sse(sse_events=sse, model=model):
            yield chunk

    return StreamingResponse(openai_stream(), media_type="text/event-stream")


__all__ = ["router"]
