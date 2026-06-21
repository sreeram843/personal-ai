"""Single-call chat path for trivial prompts (Claude/ChatGPT-style fast replies)."""

from __future__ import annotations

from typing import Dict, List, Sequence

from app.core.config import Settings
from app.schemas.chat import ChatResponse
from app.services.llm_gateway import LLMGateway
from app.services.system_prompt import get_system_prompt


async def run_fast_chat(
    *,
    query: str,
    chat_history: Sequence[Dict[str, str]],
    llm_gateway: LLMGateway,
    settings: Settings,
) -> ChatResponse:
    """Answer with one LLM call — no tools, no multi-agent pipeline."""
    messages: List[Dict[str, str]] = [{"role": "system", "content": get_system_prompt()}]
    for item in chat_history:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        role = (item.get("role") or "user").lower()
        if role in {"user", "assistant", "system"}:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": query})

    text = await llm_gateway.generate(
        messages=messages,
        model=settings.llm_default_model,
        options={"temperature": 0.3},
        provider=settings.llm_default_provider,
    )
    return ChatResponse(message=text, sources=[])


__all__ = ["run_fast_chat"]
