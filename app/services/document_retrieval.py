"""Shared user-scoped document retrieval with multi-query expansion and reranking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.ollama import OllamaClient
from app.services.corpus_synthesis import pack_corpus_synthesis, should_use_corpus_synthesis
from app.services.cross_encoder_rerank import score_with_cross_encoder
from app.services.information_routing import is_corpus_overview_query
from app.services.query_decomposition import expand_retrieval_queries
from app.services.retrieval_rerank import rerank_and_pack, wide_retrieval_limit
from app.services.sentence_window import resolve_retrieval_text
from app.services.vector_store import VectorStore


@dataclass(frozen=True)
class DocumentRetrievalResult:
    sources: List[RetrievedChunk]
    query_variants: List[str]
    candidates_considered: int
    retrieval_hops: int = 1
    attempted_queries: List[str] = field(default_factory=list)


def _merge_candidates(
    candidates_by_id: dict[str, RetrievedChunk],
    result,
    *,
    trust_lane: str = "",
) -> None:
    payload = result.payload or {}
    chunk_id = str(result.id)
    score = float(result.score)
    existing = candidates_by_id.get(chunk_id)
    if existing is not None and existing.score >= score:
        return
    metadata = {key: value for key, value in payload.items() if key != "text"}
    if trust_lane:
        metadata["trust_lane"] = trust_lane
    candidates_by_id[chunk_id] = RetrievedChunk(
        id=chunk_id,
        score=score,
        text=resolve_retrieval_text(payload),
        metadata=metadata,
    )


async def retrieve_user_documents(
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
    """Retrieve, merge, rerank, and pack document chunks for a user query."""
    query_variants = await expand_retrieval_queries(
        query,
        settings=settings,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
    )
    if not query_variants:
        return DocumentRetrievalResult(sources=[], query_variants=[], candidates_considered=0)

    embeddings = await embed_client.embed(query_variants)
    search_limit = wide_retrieval_limit(
        pack_limit=pack_limit,
        wide_top_k=settings.retrieval_wide_top_k,
        rerank_enabled=settings.retrieval_rerank_enabled,
    )
    wide_threshold = None if settings.retrieval_rerank_enabled else score_threshold

    candidates_by_id: dict[str, RetrievedChunk] = {}
    for embedding, variant in zip(embeddings, query_variants):
        results = vector_store.search(
            embedding,
            user_id=user_id,
            limit=search_limit,
            score_threshold=wide_threshold,
            query_text=variant,
            hybrid=settings.retrieval_hybrid_enabled,
        )
        for result in results:
            _merge_candidates(candidates_by_id, result, trust_lane=trust_lane)

    candidates = list(candidates_by_id.values())
    if not candidates:
        return DocumentRetrievalResult(
            sources=[],
            query_variants=query_variants,
            candidates_considered=0,
        )

    if should_use_corpus_synthesis(query, settings=settings):
        sources = pack_corpus_synthesis(
            query,
            candidates,
            settings=settings,
            pack_limit=pack_limit,
        )
    elif settings.retrieval_rerank_enabled:
        ce_scores = await score_with_cross_encoder(query, candidates, settings=settings)
        sources = rerank_and_pack(
            query,
            candidates,
            limit=min(pack_limit, len(candidates)),
            prefer_document_summaries=is_corpus_overview_query(query),
            summary_boost=settings.retrieval_summary_boost,
            cross_encoder_scores=ce_scores,
            cross_encoder_weight=settings.retrieval_cross_encoder_weight,
        )
    else:
        sources = sorted(candidates, key=lambda item: item.score, reverse=True)[:pack_limit]

    if score_threshold is not None:
        sources = [source for source in sources if source.score >= score_threshold]

    return DocumentRetrievalResult(
        sources=sources,
        query_variants=query_variants,
        candidates_considered=len(candidates),
    )


__all__ = ["DocumentRetrievalResult", "retrieve_user_documents"]
