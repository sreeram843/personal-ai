"""LLM-powered session compaction for long chat histories."""

from __future__ import annotations

from typing import Dict, List, Sequence

from app.core.config import Settings
from app.services.conversation_context import split_history_for_compaction, summarize_older_messages
from app.services.llm_gateway import LLMGateway


async def summarize_history_with_llm(
    *,
    older_messages: Sequence[Dict[str, str]],
    llm_gateway: LLMGateway,
    settings: Settings,
) -> str:
    """Summarize older turns with one cheap LLM call; fall back to heuristic bullets."""
    heuristic = summarize_older_messages(older_messages, max_summary_chars=settings.chat_history_summary_max_chars)
    if not older_messages or not settings.enable_llm_history_compaction:
        return heuristic

    transcript_lines: List[str] = []
    for item in older_messages[-12:]:
        role = str(item.get("role") or "user").upper()
        content = " ".join(str(item.get("content") or "").split())[:400]
        if content:
            transcript_lines.append(f"{role}: {content}")
    if not transcript_lines:
        return heuristic

    prompt = (
        "Summarize this conversation excerpt for future context. "
        "Keep user preferences, decisions, names, and open tasks. "
        "Use short bullet points. Max 120 words.\n\n"
        + "\n".join(transcript_lines)
    )
    try:
        result = await llm_gateway.generate_with_meta(
            messages=[{"role": "user", "content": prompt}],
            model=settings.llm_default_model,
            provider=settings.llm_default_provider,
            options={"temperature": 0.2, "max_tokens": 220},
        )
        text = (result.content or "").strip()
        if text:
            return text
    except Exception:
        pass
    return heuristic


async def build_context_efficient_messages_llm(
    *,
    system_prompt: str,
    chat_history: Sequence[Dict[str, str]],
    query: str,
    llm_gateway: LLMGateway,
    settings: Settings,
) -> List[Dict[str, str]]:
    """Like build_context_efficient_messages but uses LLM summary when enabled."""
    from app.services.conversation_context import build_context_efficient_messages

    prompt = system_prompt.strip()
    messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]

    older, recent = split_history_for_compaction(
        chat_history,
        compact_after_messages=settings.chat_history_compact_after,
        recent_messages=settings.chat_history_recent_messages,
    )
    if older:
        summary = await summarize_history_with_llm(
            older_messages=older,
            llm_gateway=llm_gateway,
            settings=settings,
        )
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "## Earlier conversation (compact summary)\n"
                        "Use this for continuity only; prioritize recent turns and the latest request.\n\n"
                        f"{summary}"
                    ),
                }
            )
    messages.extend(recent)
    normalized_query = query.strip()
    last = messages[-1] if messages else None
    if not (last and last["role"] == "user" and last["content"].strip() == normalized_query):
        messages.append({"role": "user", "content": normalized_query})
    return messages


__all__ = ["build_context_efficient_messages_llm", "summarize_history_with_llm"]
