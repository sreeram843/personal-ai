from __future__ import annotations

import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.deps import get_llm_gateway
from app.schemas.demo import DemoChatRequest, DemoChatResponse, DemoConfigResponse
from app.services.demo_quota import DemoQuotaSnapshot, get_demo_quota_store
from app.services.fast_chat import run_fast_chat
from app.services.llm_gateway import LLMGateway
from app.services.system_prompt import get_demo_system_prompt

router = APIRouter(prefix="/demo", tags=["demo"])


def _is_demo_intro_message(content: str, intro: str) -> bool:
    text = content.strip()
    if not text:
        return True
    normalized_intro = intro.strip()
    if normalized_intro and text == normalized_intro:
        return True
    return text.startswith("Try CurAI —")


def _demo_chat_history(body: DemoChatRequest, settings: Settings) -> List[Dict[str, str]]:
    intro = (settings.demo_intro or "").strip() or (
        "Try CurAI — a smart assistant with live data and tool calling. "
        f"You have {settings.demo_max_questions} free questions in this demo."
    )
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


@router.get("/config", response_model=DemoConfigResponse)
def read_demo_config(settings: Settings = Depends(_require_demo_enabled)) -> DemoConfigResponse:
    intro = (settings.demo_intro or "").strip() or (
        "Try CurAI — a smart assistant with live data and tool calling. "
        f"You have {settings.demo_max_questions} free questions in this demo."
    )
    return DemoConfigResponse(
        enabled=True,
        max_questions=settings.demo_max_questions,
        intro=intro,
    )


@router.post("/chat", response_model=DemoChatResponse)
async def demo_chat(
    body: DemoChatRequest,
    settings: Settings = Depends(_require_demo_enabled),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> DemoChatResponse:
    store = get_demo_quota_store()
    usage_before = await store.get_usage(body.session_id)
    if usage_before >= settings.demo_max_questions:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Demo question limit reached.",
                "questions_used": usage_before,
                "questions_remaining": 0,
                "limit_reached": True,
            },
        )

    history = _demo_chat_history(body, settings)

    started = time.perf_counter()
    try:
        response = await run_fast_chat(
            query=body.message.strip(),
            chat_history=history,
            llm_gateway=llm_gateway,
            settings=settings,
            system_prompt=get_demo_system_prompt(),
            max_output_tokens=settings.demo_max_output_tokens,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Demo chat failed: {exc}",
        ) from exc

    quota: DemoQuotaSnapshot = await store.increment(body.session_id, max_questions=settings.demo_max_questions)
    latency_ms = (time.perf_counter() - started) * 1000

    full_app_url = (settings.demo_full_app_url or "").strip() or None

    return DemoChatResponse(
        message=response.message,
        sources=[],
        workflow=None,
        conversation_id=None,
        live=None,
        latency_ms=latency_ms,
        questions_used=quota.used,
        questions_remaining=quota.remaining,
        limit_reached=quota.limit_reached,
        full_app_url=full_app_url,
    )


__all__ = ["router"]
