"""Expand user queries into multiple retrieval variants before embedding."""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Sequence

from app.core.config import Settings
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile

logger = logging.getLogger(__name__)

_DECOMPOSE_SYSTEM = """You expand user questions into search queries for a document database.
Return a JSON array of 1-3 short alternate search queries (strings).
Each variant should use different wording or focus on a sub-question.
Do not repeat the original verbatim. Keep each under 20 words.
Return JSON only: ["query one", "query two"]"""

_COMPOUND_SEPARATORS = (" and ", " vs ", " versus ", " compared to ", " compare ")


def _dedupe_queries(queries: Sequence[str], *, max_queries: int) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for raw in queries:
        normalized = " ".join(str(raw).split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
        if len(ordered) >= max_queries:
            break
    return ordered


def heuristic_query_variants(query: str, *, max_queries: int) -> List[str]:
    """Split compound questions without an LLM call."""
    base = query.strip()
    if not base:
        return []

    variants = [base]
    lowered = base.lower()
    for separator in _COMPOUND_SEPARATORS:
        if separator not in lowered or len(variants) >= max_queries:
            continue
        parts = re.split(re.escape(separator), base, flags=re.IGNORECASE)
        for part in parts:
            cleaned = part.strip().rstrip("?").strip()
            if cleaned and cleaned.lower() not in {item.lower() for item in variants}:
                variants.append(cleaned)
            if len(variants) >= max_queries:
                break
    return variants[:max_queries]


def _parse_query_variants(raw: str) -> List[str]:
    candidate = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", candidate, flags=re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        array_match = re.search(r"(\[[\s\S]*\])", candidate)
        if array_match:
            candidate = array_match.group(1)
    try:
        items = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


async def _llm_expand_queries(
    query: str,
    *,
    settings: Settings,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
) -> List[str]:
    response = await llm_gateway.generate(
        messages=[
            {"role": "system", "content": _DECOMPOSE_SYSTEM},
            {"role": "user", "content": query},
        ],
        model=model_profile.planner.model,
        provider=model_profile.planner.provider,
        options={"temperature": 0.2},
    )
    return _parse_query_variants(response)


async def expand_retrieval_queries(
    query: str,
    *,
    settings: Settings,
    llm_gateway: Optional[LLMGateway] = None,
    model_profile: Optional[WorkflowModelProfile] = None,
) -> List[str]:
    """Return deduped query variants for multi-query retrieval (original always first)."""
    base = query.strip()
    if not base:
        return []

    max_queries = max(1, settings.retrieval_query_decomposition_max_queries)
    if not settings.retrieval_query_decomposition_enabled:
        return [base]
    if len(base.split()) < settings.retrieval_query_decomposition_min_words:
        return [base]

    variants: List[str] = [base]
    if llm_gateway is not None and model_profile is not None:
        try:
            llm_variants = await _llm_expand_queries(
                base,
                settings=settings,
                llm_gateway=llm_gateway,
                model_profile=model_profile,
            )
            if llm_variants:
                variants.extend(llm_variants)
        except Exception:
            logger.info("LLM query decomposition failed; using heuristic fallback", exc_info=True)

    if len(variants) == 1:
        variants = heuristic_query_variants(base, max_queries=max_queries)

    return _dedupe_queries(variants, max_queries=max_queries)


__all__ = [
    "expand_retrieval_queries",
    "heuristic_query_variants",
]
