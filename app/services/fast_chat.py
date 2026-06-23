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
    system_prompt: str | None = None,
    max_output_tokens: int | None = None,
) -> ChatResponse:
    """Answer with one LLM call — no tools, no multi-agent pipeline."""
    prompt = (system_prompt or get_system_prompt()).strip()
    messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]
    for item in chat_history:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        role = (item.get("role") or "user").lower()
        if role in {"user", "assistant", "system"}:
            messages.append({"role": role, "content": content})
    normalized_query = query.strip()
    last = messages[-1] if messages else None
    if not (last and last["role"] == "user" and last["content"].strip() == normalized_query):
        messages.append({"role": "user", "content": normalized_query})

    options: Dict[str, object] = {"temperature": 0.3}
    if max_output_tokens is not None and max_output_tokens > 0:
        options["max_tokens"] = max_output_tokens

    text = await llm_gateway.generate(
        messages=messages,
        model=settings.llm_default_model,
        options=options,
        provider=settings.llm_default_provider,
    )
    return ChatResponse(message=text, sources=[])


__all__ = ["run_fast_chat"]
