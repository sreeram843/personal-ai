"""
Centralized heuristics for when to use web research vs LLM-only context,
and when Smart mode should take the full workflow path.

This reduces duplicate keyword logic and fixes the previous behavior where an
empty retrieval context (normal for /chat) forced web search on every message.
"""

from __future__ import annotations

import re
from typing import Final, List

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


def is_external_web_lookup_query(user_query: str) -> bool:
    """Public recommendation or local-entity questions that need web search, not internal docs."""
    if is_trivial_chitchat(user_query):
        return False
    if is_document_grounded_query(user_query):
        return False
    lowered = user_query.lower()
    if any(hint in lowered for hint in _LOCAL_ENTITY_HINTS):
        return True
    has_recommendation = any(re.search(pattern, lowered) for pattern in _RECOMMENDATION_PATTERNS)
    if has_recommendation and _PLACE_HINT_PATTERN.search(user_query):
        return True
    return False


def prefers_tool_agent_for_query(user_query: str) -> bool:
    """Route to the native tool agent for external factual lookups with iterative search."""
    return is_external_web_lookup_query(user_query)


def decompose_research_queries(user_query: str, *, max_queries: int = 4) -> List[str]:
    """Split multi-part comparison prompts into focused web search queries."""
    query = user_query.strip()
    if not query:
        return []

    lowered = query.lower()
    comparison_markers = ("compare", "versus", " vs ", " vs.", "winner", "better than")
    if not any(marker in lowered for marker in comparison_markers):
        return [query]

    segments = re.split(
        r"\b(?:compare|versus|vs\.?|and then|winner|with)\b",
        query,
        flags=re.IGNORECASE,
    )
    focused: List[str] = []
    for segment in segments:
        cleaned = segment.strip(" ?.,;:")
        if len(cleaned.split()) < 3:
            continue
        if cleaned.lower().startswith(("that with", "it with", "them with")):
            cleaned = cleaned.split(" ", 1)[-1].strip()
        if len(cleaned.split()) >= 3:
            focused.append(cleaned)

    if len(focused) >= 2:
        return focused[:max_queries]
    return [query]


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
    if is_external_web_lookup_query(user_query):
        return True
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

_COMPLEX_REASONING_TERMS: Final[tuple[str, ...]] = (
    "compare",
    "trade-off",
    "tradeoff",
    "analyze",
    "analysis",
    "roadmap",
    "strategy",
    "multi-step",
    "step by step",
    "cross-check",
    "synthesize",
    "audit",
    "review",
    "plan",
    "workflow",
    "versus",
    " vs ",
    " vs.",
    "recommend",
    "evaluate",
    "breaking down",
)

_CORPUS_OVERVIEW_HINTS: Final[tuple[str, ...]] = (
    "main themes",
    "main topics",
    "across all",
    "across my",
    "all my documents",
    "all my notes",
    "all my files",
    "all my uploads",
    "summarize my",
    "summary of my",
    "overview of my",
    "what do my documents",
    "what do my notes",
    "themes across",
    "topics across",
    "everything i uploaded",
    "everything i've uploaded",
)

_RECOMMENDATION_PATTERNS: Final[tuple[str, ...]] = (
    r"\bbest\b",
    r"\btop[\s-]?rated\b",
    r"\btop\s+\d",
    r"\branked\b",
    r"\brecommend(?:ed|ation|s)?\b",
    r"\bfavorite\b",
    r"\bfavourite\b",
    r"\bmust[\s-]?try\b",
)

_PLACE_HINT_PATTERN = re.compile(
    r"\b(?:in|near|around|at)\s+[A-Z][\w\s\-']{2,}|\b(?:bbq|barbecue|barbeque|restaurant)\b",
    re.IGNORECASE,
)

_LOCAL_ENTITY_HINTS: Final[tuple[str, ...]] = (
    "bbq",
    "barbecue",
    "barbeque",
    "restaurant",
    "restaurants",
    "bar ",
    " bars",
    "cafe",
    "coffee shop",
    "hotel",
    "hotels",
    "pizza",
    "sushi",
    "taco",
    "brewery",
    "winery",
    "museum",
    "attraction",
    "things to do",
)

_DOCUMENT_GROUNDED_HINTS: Final[tuple[str, ...]] = (
    "my upload",
    "my document",
    "my documents",
    "my notes",
    "my files",
    "uploaded",
    "ingested",
    "internal doc",
    "from my",
    "in my notes",
    "with citations",
    "with citation",
    "cite",
    "citation",
    "sources",
    "according to my",
    "based on my",
    "our document",
    "our notes",
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


def is_document_grounded_query(user_query: str) -> bool:
    """True when the user is likely asking about their ingested documents."""
    lowered = user_query.lower()
    return any(hint in lowered for hint in _DOCUMENT_GROUNDED_HINTS)


def is_corpus_overview_query(user_query: str) -> bool:
    """True when the user wants themes or synthesis across many documents."""
    lowered = user_query.lower()
    if any(hint in lowered for hint in _CORPUS_OVERVIEW_HINTS):
        return True
    if re.search(r"\bthemes?\b.+\bacross\b", lowered):
        return True
    if re.search(r"\b(topics?|documents?|notes?|files?)\b.+\bacross\b", lowered):
        return True
    return False


def should_route_chat_toward_orchestrated(user_query: str) -> bool:
    """Route to the multi-agent workflow when the prompt needs deep synthesis."""
    if is_trivial_chitchat(user_query):
        return False
    if prefers_tool_agent_for_query(user_query):
        return False

    words = user_query.split()
    lowered = user_query.lower()

    if any(term in lowered for term in _COMPLEX_REASONING_TERMS):
        return True
    if len(words) >= 24:
        return True

    if should_prioritize_fresh_web_data(user_query):
        if len(words) >= 10:
            return True
        if any(hint in lowered for hint in _FRESH_WORKFLOW_HINTS):
            return True
        if re.search(r"\b(why|how)\s+.{12,}", lowered):
            return True
        return False

    if len(words) >= 12 and re.search(r"\b(why|how)\s+.{8,}", lowered):
        return True
    return False


def should_route_chat_toward_tools(user_query: str) -> bool:
    """Route to the tool agent for factual, on-demand retrieval without full workflow."""
    if is_trivial_chitchat(user_query):
        return False
    if should_route_chat_toward_orchestrated(user_query):
        return False
    return True

