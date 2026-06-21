"""
Centralized heuristics for when to use web research vs LLM-only context,
and when Smart mode should take the full workflow path.

This reduces duplicate keyword logic and fixes the previous behavior where an
empty retrieval context (normal for /chat) forced web search on every message.
"""

from __future__ import annotations

import re
from typing import Final

from app.services.web_search import should_prioritize_fresh_web_data

# Greetings and acknowledgements — do not call web search for these.
_QUICK_SOCIAL: Final[set[str]] = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank you",
    "yo",
}
_TRIVIAL_ONE_WORD: Final[set[str]] = {
    "ok",
    "k",
    "yes",
    "no",
    "yep",
    "nope",
    "lol",
    "haha",
    "sure",
    "nice",
    "hi",
    "bye",
    "thx",
}


def is_quick_social_utterance(text: str) -> bool:
    """Small talk that should stay on the cheap /chat path in Smart mode."""
    t = text.lower().strip()
    words = t.split()
    if len(words) <= 4 and t in _QUICK_SOCIAL:
        return True
    return False


def is_trivial_chitchat(text: str) -> bool:
    """True when web research would be wasteful (short acknowledgements, etc.)."""
    t = text.lower().strip()
    if not t:
        return True
    if len(t) <= 2 and t.isalnum():
        return True
    words = t.split()
    if len(words) == 1 and words[0] in _TRIVIAL_ONE_WORD:
        return True
    if is_quick_social_utterance(text):
        return True
    return False


def should_run_web_research(user_query: str, has_internal_hits: bool) -> bool:
    """
    Whether the orchestration *researcher* step should call the web search API.

    We only search when the query looks time-sensitive or explicitly external
    (``should_prioritize_fresh_web_data``), never solely because the corpus
    had no RAG hit — that was the main source of redundant DuckDuckGo calls
    in ``/chat`` (no retriever) and in ``/rag`` when the vector store is empty.
    The second argument is reserved for a future RAG+web policy (e.g. score
    thresholds).
    """
    if is_trivial_chitchat(user_query):
        return False
    return should_prioritize_fresh_web_data(user_query)


# Fresh queries that are long or comparative probably justify the planner+workflow
# path; short "price" / "fx" style questions are better served by the static RAG-style
# pipeline (and live-data short-circuit may already have answered).
_FRESH_WORKFLOW_HINTS: Final[tuple[str, ...]] = (
    "compare",
    "versus",
    " vs ",
    " vs.",
    "analysis",
    "roadmap",
    "strategy",
    "evaluate",
    "breaking down",
    "trade-off",
    "tradeoff",
)


def should_route_smart_toward_workflow(user_query: str) -> bool:
    """
    When Smart mode sees a *fresh* query, choose workflow only if it is likely
    complex enough to benefit from the dynamic planner. Short, factual live-style
    prompts stay on the static RAG pipeline (still with researcher gated by
    should_run_web_research).
    """
    if not should_prioritize_fresh_web_data(user_query):
        return False
    if is_trivial_chitchat(user_query):
        return False
    words = user_query.split()
    if len(words) >= 6:
        return True
    lowered = user_query.lower()
    if any(h in lowered for h in _FRESH_WORKFLOW_HINTS):
        return True
    return bool(re.search(r"\b(why|how|what)\s+.{8,}", lowered))

