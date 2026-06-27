"""Compact conversation history for small LLM context windows."""

from __future__ import annotations

from typing import Dict, List, Sequence


def _normalize_role(role: str) -> str:
    value = (role or "user").strip().lower()
    if value in {"user", "assistant", "system"}:
        return value
    return "user"


def _truncate_text(text: str, max_chars: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def summarize_older_messages(
    messages: Sequence[Dict[str, str]],
    *,
    max_summary_chars: int = 800,
    max_line_chars: int = 150,
) -> str:
    """Build a compact bullet summary of older turns without an extra LLM call."""
    lines: List[str] = []
    for item in messages:
        role = _normalize_role(str(item.get("role") or "user")).upper()
        content = _truncate_text(str(item.get("content") or ""), max_line_chars)
        if content:
            lines.append(f"- {role}: {content}")
    if not lines:
        return ""
    summary = "\n".join(lines)
    if len(summary) <= max_summary_chars:
        return summary
    trimmed = summary[:max_summary_chars]
    last_break = trimmed.rfind("\n")
    if last_break > max_summary_chars // 2:
        trimmed = trimmed[:last_break]
    return trimmed.rstrip() + "\n- …"


def split_history_for_compaction(
    chat_history: Sequence[Dict[str, str]],
    *,
    compact_after_messages: int,
    recent_messages: int,
) -> tuple[Sequence[Dict[str, str]], Sequence[Dict[str, str]]]:
    """Split history into older (to summarize) and recent (to keep verbatim)."""
    normalized = [
        {"role": _normalize_role(str(item.get("role") or "user")), "content": str(item.get("content") or "").strip()}
        for item in chat_history
        if str(item.get("content") or "").strip()
    ]
    if len(normalized) <= compact_after_messages:
        return [], normalized
    keep = max(1, recent_messages)
    if keep >= len(normalized):
        return [], normalized
    return normalized[:-keep], normalized[-keep:]


def build_context_efficient_messages(
    *,
    system_prompt: str,
    chat_history: Sequence[Dict[str, str]],
    query: str,
    compact_after_messages: int = 6,
    recent_messages: int = 4,
    summary_max_chars: int = 800,
) -> List[Dict[str, str]]:
    """
    Build chat messages using rolling summary + recent turns.

    When history is short, behavior matches a plain history append.
    When history is long, older turns are summarized into one system block.
    """
    prompt = system_prompt.strip()
    messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]

    older, recent = split_history_for_compaction(
        chat_history,
        compact_after_messages=compact_after_messages,
        recent_messages=recent_messages,
    )
    if older:
        summary = summarize_older_messages(older, max_summary_chars=summary_max_chars)
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "## Earlier conversation (compact summary)\n"
                        "Use this for continuity only; prioritize the recent turns and latest user request.\n\n"
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


__all__ = [
    "build_context_efficient_messages",
    "split_history_for_compaction",
    "summarize_older_messages",
]
