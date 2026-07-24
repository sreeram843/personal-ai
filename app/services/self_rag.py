"""Self-RAG retrieval retry loop: assess evidence, refine query, retrieve again."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services.document_retrieval import DocumentRetrievalResult, retrieve_user_documents
from app.services.corpus_synthesis import pack_corpus_synthesis, should_use_corpus_synthesis
from app.services.cross_encoder_rerank import score_with_cross_encoder
from app.services.information_routing import is_corpus_overview_query
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.ollama import OllamaClient
from app.services.query_decomposition import heuristic_query_variants
from app.services.retrieval_rerank import lexical_overlap_score, rerank_and_pack
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """You judge whether retrieved document excerpts can answer the user question.
Return JSON only:
{"sufficient": true|false, "follow_up_query": "short search query or empty string"}
Set sufficient=true only when the excerpts clearly contain enough facts to answer.
If insufficient, follow_up_query should target missing facts with different wording."""


@dataclass(frozen=True)
class RetrievalAssessment:
    sufficient: bool
    follow_up_query: str = ""


def merge_retrieval_sources(
    existing: dict[str, RetrievedChunk],
    sources: Sequence[RetrievedChunk],
) -> None:
    for source in sources:
        current = existing.get(source.id)
        if current is None or source.score > current.score:
            existing[source.id] = source


def heuristic_assess_retrieval(
    query: str,
    sources: Sequence[RetrievedChunk],
    *,
    settings: Settings,
) -> RetrievalAssessment:
    if not sources:
        follow_up = _heuristic_follow_up_query(query, attempted=[query])
        return RetrievalAssessment(sufficient=False, follow_up_query=follow_up)

    ranked = sorted(sources, key=lambda item: item.score, reverse=True)
    top = ranked[0]
    top_score = float(top.score)
    lexical = lexical_overlap_score(query, top.text)

    if top_score >= settings.self_rag_min_top_score and lexical >= settings.self_rag_min_lexical_overlap:
        return RetrievalAssessment(sufficient=True)

    follow_up = _heuristic_follow_up_query(query, attempted=[query])
    return RetrievalAssessment(sufficient=False, follow_up_query=follow_up)


def _heuristic_follow_up_query(query: str, *, attempted: Sequence[str]) -> str:
    attempted_keys = {" ".join(item.split()).lower() for item in attempted if item.strip()}
    for variant in heuristic_query_variants(query, max_queries=4):
        key = " ".join(variant.split()).lower()
        if key not in attempted_keys:
            return variant

    stripped = re.sub(
        r"^(what|who|when|where|why|how)\s+(is|are|was|were|do|does|did)\s+",
        "",
        query,
        flags=re.IGNORECASE,
    )
    stripped = stripped.strip(" ?.")
    if stripped and stripped.lower() not in attempted_keys:
        return stripped

    words = [word for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{1,}", query) if len(word) > 2]
    if len(words) >= 3:
        condensed = " ".join(words[-3:])
        if condensed.lower() not in attempted_keys:
            return condensed
    if len(words) >= 2:
        condensed = " ".join(words[:3])
        if condensed.lower() not in attempted_keys:
            return condensed
    return ""


def _parse_assessment(raw: str) -> Optional[RetrievalAssessment]:
    candidate = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate, flags=re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        object_match = re.search(r"(\{[\s\S]*\})", candidate)
        if object_match:
            candidate = object_match.group(1)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    sufficient = bool(payload.get("sufficient"))
    follow_up = str(payload.get("follow_up_query") or "").strip()
    return RetrievalAssessment(sufficient=sufficient, follow_up_query=follow_up)


def _format_evidence_for_judge(sources: Sequence[RetrievedChunk], *, max_chars: int = 900) -> str:
    lines: List[str] = []
    total = 0
    for index, source in enumerate(sources[:4], start=1):
        metadata = source.metadata or {}
        label = str(metadata.get("path") or metadata.get("title") or metadata.get("name") or source.id)
        excerpt = " ".join(source.text.split())
        if len(excerpt) > 220:
            excerpt = excerpt[:217].rstrip() + "..."
        line = f"[{index}] {label}: {excerpt}"
        next_total = total + len(line) + 1
        if lines and next_total > max_chars:
            break
        lines.append(line)
        total = next_total
    return "\n".join(lines)


async def llm_assess_retrieval(
    query: str,
    sources: Sequence[RetrievedChunk],
    *,
    settings: Settings,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
) -> Optional[RetrievalAssessment]:
    evidence = _format_evidence_for_judge(sources)
    response = await llm_gateway.generate(
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {
                "role": "user",
                "content": f"Question:\n{query}\n\nRetrieved excerpts:\n{evidence or '(none)'}",
            },
        ],
        model=model_profile.planner.model,
        provider=model_profile.planner.provider,
        options={"temperature": 0.0},
    )
    return _parse_assessment(response)


async def assess_retrieval_sufficiency(
    query: str,
    sources: Sequence[RetrievedChunk],
    *,
    settings: Settings,
    attempted_queries: Sequence[str],
    llm_gateway: Optional[LLMGateway] = None,
    model_profile: Optional[WorkflowModelProfile] = None,
) -> RetrievalAssessment:
    heuristic = heuristic_assess_retrieval(query, sources, settings=settings)
    if heuristic.sufficient:
        return heuristic

    if (
        settings.self_rag_use_llm_judge
        and llm_gateway is not None
        and model_profile is not None
        and sources
    ):
        try:
            llm_result = await llm_assess_retrieval(
                query,
                sources,
                settings=settings,
                llm_gateway=llm_gateway,
                model_profile=model_profile,
            )
            if llm_result is not None:
                if llm_result.sufficient:
                    return llm_result
                follow_up = llm_result.follow_up_query or heuristic.follow_up_query
                if follow_up:
                    return RetrievalAssessment(sufficient=False, follow_up_query=follow_up)
        except Exception:
            logger.info("Self-RAG LLM judge failed; using heuristic follow-up", exc_info=True)

    follow_up = heuristic.follow_up_query or _heuristic_follow_up_query(query, attempted=attempted_queries)
    return RetrievalAssessment(sufficient=False, follow_up_query=follow_up)


def _pack_merged_sources(
    query: str,
    sources: Sequence[RetrievedChunk],
    *,
    settings: Settings,
    pack_limit: int,
    score_threshold: Optional[float],
    cross_encoder_scores: Optional[Sequence[float]] = None,
) -> List[RetrievedChunk]:
    candidates = list(sources)
    if not candidates:
        return []

    if should_use_corpus_synthesis(query, settings=settings):
        packed = pack_corpus_synthesis(
            query,
            candidates,
            settings=settings,
            pack_limit=pack_limit,
        )
    elif settings.retrieval_rerank_enabled:
        packed = rerank_and_pack(
            query,
            candidates,
            limit=min(pack_limit, len(candidates)),
            prefer_document_summaries=is_corpus_overview_query(query),
            summary_boost=settings.retrieval_summary_boost,
            cross_encoder_scores=cross_encoder_scores,
            cross_encoder_weight=settings.retrieval_cross_encoder_weight,
        )
    else:
        packed = sorted(candidates, key=lambda item: item.score, reverse=True)[:pack_limit]

    if score_threshold is not None:
        packed = [source for source in packed if source.score >= score_threshold]
    return packed


async def retrieve_user_documents_with_self_rag(
    *,
    query: str,
    user_id: str,
    embed_client: OllamaClient,
    vector_store: VectorStore,
    settings: Settings,
    pack_limit: int,
    score_threshold: Optional[float] = None,
    llm_gateway: Optional[LLMGateway] = None,
    model_profile: Optional[WorkflowModelProfile] = None,
    trust_lane: str = "",
) -> DocumentRetrievalResult:
    """Retrieve with up to N hops when initial evidence looks insufficient."""
    if not settings.enable_self_rag_retry or settings.self_rag_max_hops <= 1:
        return await retrieve_user_documents(
            query=query,
            user_id=user_id,
            embed_client=embed_client,
            vector_store=vector_store,
            settings=settings,
            pack_limit=pack_limit,
            score_threshold=score_threshold,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            trust_lane=trust_lane,
        )

    merged_by_id: dict[str, RetrievedChunk] = {}
    attempted_queries: List[str] = []
    query_variants: List[str] = []
    candidates_considered = 0
    current_query = query.strip()
    hops = 0
    max_hops = max(1, settings.self_rag_max_hops)

    while hops < max_hops:
        hops += 1
        if not current_query:
            break
        attempted_queries.append(current_query)

        hop_result = await retrieve_user_documents(
            query=current_query,
            user_id=user_id,
            embed_client=embed_client,
            vector_store=vector_store,
            settings=settings,
            pack_limit=pack_limit,
            score_threshold=None if settings.retrieval_rerank_enabled else score_threshold,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            trust_lane=trust_lane,
        )
        candidates_considered += hop_result.candidates_considered
        for variant in hop_result.query_variants:
            if variant not in query_variants:
                query_variants.append(variant)
        merge_retrieval_sources(merged_by_id, hop_result.sources)

        if hops >= max_hops:
            break

        assessment = await assess_retrieval_sufficiency(
            query,
            list(merged_by_id.values()),
            settings=settings,
            attempted_queries=attempted_queries,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
        )
        if assessment.sufficient:
            break

        follow_up = assessment.follow_up_query.strip()
        if not follow_up:
            break
        follow_up_key = " ".join(follow_up.split()).lower()
        if follow_up_key in {" ".join(item.split()).lower() for item in attempted_queries}:
            break
        current_query = follow_up

    merged = list(merged_by_id.values())
    ce_scores = await score_with_cross_encoder(query, merged, settings=settings)
    sources = _pack_merged_sources(
        query,
        merged,
        settings=settings,
        pack_limit=pack_limit,
        score_threshold=score_threshold,
        cross_encoder_scores=ce_scores,
    )
    return DocumentRetrievalResult(
        sources=sources,
        query_variants=query_variants,
        candidates_considered=candidates_considered,
        retrieval_hops=hops,
        attempted_queries=attempted_queries,
    )


__all__ = [
    "RetrievalAssessment",
    "assess_retrieval_sufficiency",
    "heuristic_assess_retrieval",
    "merge_retrieval_sources",
    "retrieve_user_documents_with_self_rag",
]
