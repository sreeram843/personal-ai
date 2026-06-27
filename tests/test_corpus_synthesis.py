"""Tests for GraphRAG/RAPTOR-lite corpus synthesis retrieval."""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.schemas.chat import RetrievedChunk
from app.services.corpus_synthesis import pack_corpus_synthesis, should_use_corpus_synthesis
from app.services.document_graph import extract_document_graph_signals, graph_overlap_score
from app.services.document_retrieval import retrieve_user_documents
from app.services.document_summary import DOCUMENT_SUMMARY_CHUNK_TYPE


def _chunk(
    chunk_id: str,
    *,
    score: float,
    text: str,
    document_id: str,
    chunk_type: str = "sentence_window",
    graph_entities: list[str] | None = None,
) -> RetrievedChunk:
    metadata = {
        "path": f"{document_id}.md",
        "document_id": document_id,
        "chunk_type": chunk_type,
    }
    if graph_entities:
        metadata["graph_entities"] = graph_entities
    return RetrievedChunk(id=chunk_id, score=score, text=text, metadata=metadata)


def test_extract_document_graph_signals_finds_entities_and_topics() -> None:
    signals = extract_document_graph_signals(
        "Project Atlas roadmap covers Kubernetes rollout. Budget planning increased in Q3."
    )
    assert "Project Atlas" in signals["graph_entities"]
    assert "kubernetes" in signals["graph_topics"] or "rollout" in signals["graph_topics"]


def test_graph_overlap_score_prefers_matching_entities() -> None:
    query_signals = {"entities": {"project atlas"}, "topics": {"budget"}}
    high = {"graph_entities": ["Project Atlas"], "graph_topics": ["budget", "roadmap"]}
    low = {"graph_entities": ["Other Team"], "graph_topics": ["cafeteria"]}
    assert graph_overlap_score(query_signals, high) > graph_overlap_score(query_signals, low)


def test_pack_corpus_synthesis_selects_one_summary_per_document() -> None:
    candidates = [
        _chunk(
            "sum-a",
            score=0.95,
            text="Document summary (a.md): Budget planning overview.",
            document_id="a.md",
            chunk_type=DOCUMENT_SUMMARY_CHUNK_TYPE,
            graph_entities=["Budget Planning"],
        ),
        _chunk(
            "sum-b",
            score=0.90,
            text="Document summary (b.md): Hiring roadmap overview.",
            document_id="b.md",
            chunk_type=DOCUMENT_SUMMARY_CHUNK_TYPE,
            graph_entities=["Hiring Roadmap"],
        ),
        _chunk(
            "detail-a",
            score=0.99,
            text="Unrelated picnic schedule in a.md",
            document_id="a.md",
        ),
    ]
    packed = pack_corpus_synthesis(
        "What are the main themes across my documents?",
        candidates,
        settings=Settings(
            enable_corpus_synthesis=True,
            corpus_synthesis_max_documents=2,
            corpus_synthesis_include_supporting_chunks=False,
        ),
        pack_limit=2,
    )
    assert len(packed) == 2
    assert {item.id for item in packed} == {"sum-a", "sum-b"}


def test_pack_corpus_synthesis_adds_graph_linked_neighbor() -> None:
    candidates = [
        _chunk(
            "sum-a",
            score=0.95,
            text="Document summary (a.md): Project Atlas budget planning.",
            document_id="a.md",
            chunk_type=DOCUMENT_SUMMARY_CHUNK_TYPE,
            graph_entities=["Project Atlas"],
        ),
        _chunk(
            "sum-b",
            score=0.70,
            text="Document summary (b.md): Project Atlas hiring roadmap.",
            document_id="b.md",
            chunk_type=DOCUMENT_SUMMARY_CHUNK_TYPE,
            graph_entities=["Project Atlas"],
        ),
        _chunk(
            "sum-c",
            score=0.92,
            text="Document summary (c.md): Cafeteria menu updates.",
            document_id="c.md",
            chunk_type=DOCUMENT_SUMMARY_CHUNK_TYPE,
            graph_entities=["Cafeteria"],
        ),
    ]
    packed = pack_corpus_synthesis(
        "What are the main themes across my documents about Project Atlas?",
        candidates,
        settings=Settings(
            enable_corpus_synthesis=True,
            corpus_synthesis_max_documents=1,
            corpus_synthesis_include_supporting_chunks=False,
            corpus_synthesis_graph_boost=0.2,
        ),
        pack_limit=3,
    )
    ids = {item.id for item in packed}
    assert "sum-a" in ids
    assert "sum-b" in ids


class _CorpusVectorStore:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None):
        return [
            type(
                "Result",
                (),
                {
                    "id": "sum-a",
                    "score": 0.82,
                    "payload": {
                        "text": "Document summary (a.md): Budget planning overview.",
                        "path": "a.md",
                        "document_id": "a.md",
                        "chunk_type": DOCUMENT_SUMMARY_CHUNK_TYPE,
                        "graph_entities": ["Budget Planning"],
                    },
                },
            )(),
            type(
                "Result",
                (),
                {
                    "id": "sum-b",
                    "score": 0.80,
                    "payload": {
                        "text": "Document summary (b.md): Hiring roadmap overview.",
                        "path": "b.md",
                        "document_id": "b.md",
                        "chunk_type": DOCUMENT_SUMMARY_CHUNK_TYPE,
                        "graph_entities": ["Hiring Roadmap"],
                    },
                },
            )(),
            type(
                "Result",
                (),
                {
                    "id": "detail-noise",
                    "score": 0.99,
                    "payload": {
                        "text": "Office picnic schedule",
                        "path": "noise.md",
                        "document_id": "noise.md",
                        "chunk_type": "sentence_window",
                    },
                },
            )(),
        ]


class _StubEmbed:
    async def embed(self, inputs):
        return [[0.1, 0.2, 0.3] for _ in inputs]


def test_retrieve_user_documents_uses_corpus_synthesis_for_overview_queries() -> None:
    result = asyncio.run(
        retrieve_user_documents(
            query="What are the main themes across my documents?",
            user_id="user-1",
            embed_client=_StubEmbed(),
            vector_store=_CorpusVectorStore(),
            settings=Settings(
                enable_corpus_synthesis=True,
                retrieval_query_decomposition_enabled=False,
                retrieval_rerank_enabled=True,
                default_top_k=2,
            ),
            pack_limit=2,
        )
    )
    assert should_use_corpus_synthesis("What are the main themes across my documents?", settings=Settings())
    assert len(result.sources) == 2
    assert all(
        (source.metadata or {}).get("chunk_type") == DOCUMENT_SUMMARY_CHUNK_TYPE for source in result.sources
    )
