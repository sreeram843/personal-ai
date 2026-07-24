from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.deps import get_live_data_manager, get_llm_gateway, get_web_search
from app.schemas.chat import ChatResponse
from app.schemas.demo import DemoChatRequest, DemoChatResponse, DemoConfigResponse
from app.services.demo_live_teaser import (
    default_demo_intro,
    demo_suggested_prompts,
    fetch_demo_live_teaser,
)
from app.services.demo_llm_retry import (
    PROVIDER_RATE_LIMIT_MESSAGE,
    is_provider_rate_limit,
    run_with_provider_rate_limit_retry,
)
from app.services.demo_quota import DemoQuotaSnapshot, get_demo_quota_store
from app.services.fast_chat import run_fast_chat
from app.services.live_data_manager import LiveDataManager
from app.services.llm_gateway import LLMGateway
from app.services.system_prompt import get_demo_system_prompt
from app.services.web_search import WebSearchService

router = APIRouter(prefix="/demo", tags=["demo"])


def _is_demo_intro_message(content: str, intro: str) -> bool:
    text = content.strip()
    if not text:
        return True
    normalized_intro = intro.strip()
    if normalized_intro and text == normalized_intro:
        return True
    return text.startswith("Try CurAI —")


def _resolve_demo_intro(settings: Settings) -> str:
    return (settings.demo_intro or "").strip() or default_demo_intro(settings.demo_max_questions)


def _full_app_url(settings: Settings) -> Optional[str]:
    return (settings.demo_full_app_url or "").strip() or None


def _demo_chat_history(body: DemoChatRequest, settings: Settings) -> List[Dict[str, str]]:
    intro = _resolve_demo_intro(settings)
    history: List[Dict[str, str]] = []
    for item in body.messages:
        content = item.content.strip()
        if not content:
            continue
        if item.role == "assistant" and _is_demo_intro_message(content, intro):
            continue
        history.append({"role": item.role, "content": content})
    return history[-settings.demo_max_history_messages :]


def _require_demo_enabled(settings: Settings = Depends(get_settings)) -> Settings:
    if not settings.demo_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo is not enabled")
    return settings


def _encode_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _quota_http_detail(usage: int) -> dict[str, Any]:
    return {
        "message": "Demo question limit reached.",
        "questions_used": usage,
        "questions_remaining": 0,
        "limit_reached": True,
    }


def _provider_rate_limit_detail() -> dict[str, Any]:
    return {
        "message": PROVIDER_RATE_LIMIT_MESSAGE,
        "code": "provider_rate_limit",
        "limit_reached": False,
    }


async def _run_demo_fast_chat(
    *,
    query: str,
    history: Sequence[Dict[str, str]],
    llm_gateway: LLMGateway,
    settings: Settings,
    system_prompt: str,
) -> ChatResponse:
    async def _once() -> ChatResponse:
        return await run_fast_chat(
            query=query,
            chat_history=history,
            llm_gateway=llm_gateway,
            settings=settings,
            system_prompt=system_prompt,
            max_output_tokens=settings.demo_max_output_tokens,
        )

    return await run_with_provider_rate_limit_retry(_once, max_attempts=3)


def _http_exception_for_demo_llm_failure(exc: Exception) -> HTTPException:
    if is_provider_rate_limit(exc):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_provider_rate_limit_detail(),
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Demo chat failed: {exc}",
    )


async def _build_demo_chat_response(
    *,
    body: DemoChatRequest,
    settings: Settings,
    llm_gateway: LLMGateway,
    live_data: LiveDataManager,
    web_search: WebSearchService,
) -> DemoChatResponse:
    store = get_demo_quota_store()
    usage_before = await store.get_usage(body.session_id)
    if usage_before >= settings.demo_max_questions:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_quota_http_detail(usage_before),
        )

    history = _demo_chat_history(body, settings)
    query = body.message.strip()
    started = time.perf_counter()

    teaser = await fetch_demo_live_teaser(
        query=query,
        live_data=live_data,
        web_search=web_search,
        settings=settings,
    )

    system_prompt = get_demo_system_prompt()
    if teaser.context:
        system_prompt = f"{system_prompt.rstrip()}\n\n{teaser.context}"

    try:
        response = await _run_demo_fast_chat(
            query=query,
            history=history,
            llm_gateway=llm_gateway,
            settings=settings,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        raise _http_exception_for_demo_llm_failure(exc) from exc

    quota: DemoQuotaSnapshot = await store.increment(
        body.session_id, max_questions=settings.demo_max_questions
    )
    latency_ms = (time.perf_counter() - started) * 1000

    return DemoChatResponse(
        message=response.message,
        sources=[],
        workflow=None,
        conversation_id=None,
        live=teaser.live,
        blocks=teaser.blocks,
        latency_ms=latency_ms,
        questions_used=quota.used,
        questions_remaining=quota.remaining,
        limit_reached=quota.limit_reached,
        full_app_url=_full_app_url(settings),
    )


@router.get("/config", response_model=DemoConfigResponse)
def read_demo_config(settings: Settings = Depends(_require_demo_enabled)) -> DemoConfigResponse:
    return DemoConfigResponse(
        enabled=True,
        max_questions=settings.demo_max_questions,
        intro=_resolve_demo_intro(settings),
        full_app_url=_full_app_url(settings),
        suggested_prompts=demo_suggested_prompts(),
    )


@router.post("/chat", response_model=DemoChatResponse)
async def demo_chat(
    body: DemoChatRequest,
    settings: Settings = Depends(_require_demo_enabled),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    web_search: WebSearchService = Depends(get_web_search),
) -> DemoChatResponse:
    return await _build_demo_chat_response(
        body=body,
        settings=settings,
        llm_gateway=llm_gateway,
        live_data=live_data,
        web_search=web_search,
    )


@router.post("/chat/stream")
async def demo_chat_stream(
    body: DemoChatRequest,
    settings: Settings = Depends(_require_demo_enabled),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    live_data: LiveDataManager = Depends(get_live_data_manager),
    web_search: WebSearchService = Depends(get_web_search),
) -> StreamingResponse:
    """SSE demo chat: status events while fetching live context, then final response."""

    async def event_stream() -> AsyncIterator[str]:
        try:
            store = get_demo_quota_store()
            usage_before = await store.get_usage(body.session_id)
            if usage_before >= settings.demo_max_questions:
                yield _encode_sse({"type": "error", "detail": _quota_http_detail(usage_before)})
                return

            history = _demo_chat_history(body, settings)
            query = body.message.strip()
            started = time.perf_counter()

            teaser = await fetch_demo_live_teaser(
                query=query,
                live_data=live_data,
                web_search=web_search,
                settings=settings,
            )
            if teaser.intent and teaser.status_message:
                yield _encode_sse({"type": "status", "message": teaser.status_message})

            system_prompt = get_demo_system_prompt()
            if teaser.context:
                system_prompt = f"{system_prompt.rstrip()}\n\n{teaser.context}"

            yield _encode_sse({"type": "status", "message": "Writing reply…"})

            try:
                response = await _run_demo_fast_chat(
                    query=query,
                    history=history,
                    llm_gateway=llm_gateway,
                    settings=settings,
                    system_prompt=system_prompt,
                )
            except Exception as exc:
                if is_provider_rate_limit(exc):
                    yield _encode_sse({"type": "error", "detail": _provider_rate_limit_detail()})
                else:
                    yield _encode_sse(
                        {
                            "type": "error",
                            "detail": {
                                "message": f"Demo chat failed: {exc}",
                                "limit_reached": False,
                            },
                        }
                    )
                return

            quota: DemoQuotaSnapshot = await store.increment(
                body.session_id, max_questions=settings.demo_max_questions
            )
            latency_ms = (time.perf_counter() - started) * 1000
            payload = DemoChatResponse(
                message=response.message,
                sources=[],
                workflow=None,
                conversation_id=None,
                live=teaser.live,
                blocks=teaser.blocks,
                latency_ms=latency_ms,
                questions_used=quota.used,
                questions_remaining=quota.remaining,
                limit_reached=quota.limit_reached,
                full_app_url=_full_app_url(settings),
            )
            yield _encode_sse({"type": "final", "response": payload.model_dump()})
        except Exception as exc:
            yield _encode_sse(
                {"type": "error", "detail": {"message": str(exc), "limit_reached": False}}
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


__all__ = ["router"]
