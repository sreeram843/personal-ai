"""Single-call chat path for trivial prompts (Claude/ChatGPT-style fast replies)."""

from __future__ import annotations

from typing import Dict, Sequence

from app.core.config import Settings
from app.schemas.chat import ChatResponse
from app.services.conversation_context import build_context_efficient_messages
from app.services.session_compaction import build_context_efficient_messages_llm
from app.services.llm_gateway import LLMGateway
from app.services.prompt_context import augment_system_prompt
from app.services.sentiment_routing import detect_sentiment
from app.services.system_prompt import get_system_prompt
from app.services.user_memory import UserMemoryStore


async def run_fast_chat(
    *,
    query: str,
    chat_history: Sequence[Dict[str, str]],
    llm_gateway: LLMGateway,
    settings: Settings,
    system_prompt: str | None = None,
    max_output_tokens: int | None = None,
    user_id: str | None = None,
    user_memory_store: UserMemoryStore | None = None,
) -> ChatResponse:
    """Answer with one LLM call — no tools, no multi-agent pipeline."""
    base_prompt = (system_prompt or get_system_prompt()).strip()
    prompt = augment_system_prompt(
        base_prompt,
        user_query=query,
        user_id=user_id,
        settings=settings,
        user_memory_store=user_memory_store,
    )
    if settings.enable_llm_history_compaction:
        messages = await build_context_efficient_messages_llm(
            system_prompt=prompt,
            chat_history=chat_history,
            query=query,
            llm_gateway=llm_gateway,
            settings=settings,
        )
    else:
        messages = build_context_efficient_messages(
            system_prompt=prompt,
            chat_history=chat_history,
            query=query,
            compact_after_messages=settings.chat_history_compact_after,
            recent_messages=settings.chat_history_recent_messages,
            summary_max_chars=settings.chat_history_summary_max_chars,
        )

    options: Dict[str, object] = {"temperature": 0.3}
    if max_output_tokens is not None and max_output_tokens > 0:
        options["max_tokens"] = max_output_tokens

    from app.services.settings_store import resolve_chat_default_route

    provider, model = resolve_chat_default_route(settings)
    result = await llm_gateway.generate_with_meta(
        messages=messages,
        model=model,
        options=options,
        provider=provider,
    )
    sentiment = detect_sentiment(query) if settings.enable_sentiment_tone else None
    return ChatResponse(
        message=result.content,
        sources=[],
        reasoning=result.reasoning_content or None,
        sentiment=sentiment,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


__all__ = ["run_fast_chat"]
