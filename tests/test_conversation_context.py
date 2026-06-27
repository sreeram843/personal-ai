"""Tests for rolling conversation context compaction."""

from __future__ import annotations

from app.services.conversation_context import (
    build_context_efficient_messages,
    split_history_for_compaction,
    summarize_older_messages,
)


def _history(n_turns: int) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for idx in range(n_turns):
        messages.append({"role": "user", "content": f"User message {idx}"})
        messages.append({"role": "assistant", "content": f"Assistant reply {idx}"})
    return messages


def test_short_history_is_not_compacted() -> None:
    history = _history(2)
    older, recent = split_history_for_compaction(history, compact_after_messages=6, recent_messages=4)
    assert older == []
    assert len(recent) == 4


def test_long_history_splits_into_summary_and_recent() -> None:
    history = _history(6)
    older, recent = split_history_for_compaction(history, compact_after_messages=6, recent_messages=4)
    assert len(older) == 8
    assert len(recent) == 4
    assert recent[-1]["content"] == "Assistant reply 5"


def test_summarize_older_messages_truncates_lines() -> None:
    history = [{"role": "user", "content": "x" * 300}]
    summary = summarize_older_messages(history, max_summary_chars=500, max_line_chars=80)
    assert "USER:" in summary
    assert len(summary) < 300


def test_build_context_efficient_messages_injects_summary_block() -> None:
    history = _history(8)
    messages = build_context_efficient_messages(
        system_prompt="You are helpful.",
        chat_history=history,
        query="Latest question",
        compact_after_messages=6,
        recent_messages=4,
    )
    contents = "\n".join(item["content"] for item in messages)
    assert sum(1 for item in messages if item["role"] == "system") == 2
    assert "Earlier conversation (compact summary)" in contents
    assert "User message 0" in contents
    assert "Assistant reply 7" in contents
    assert messages[-1] == {"role": "user", "content": "Latest question"}
