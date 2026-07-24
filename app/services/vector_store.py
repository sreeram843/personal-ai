from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchText,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.services.sparse_retrieval import merge_dense_and_keyword_hits, significant_query_terms


USER_ID_PAYLOAD_KEY = "user_id"


logger = logging.getLogger(__name__)


@dataclass
class StoredDocument:
    """Internal representation for a document chunk stored in Qdrant."""

    text: str
    metadata: Dict[str, Any]
    id: Optional[Union[str, int]] = None


class VectorStore:
    """Wrapper around Qdrant for common vector database operations."""

    def __init__(
        self,
        *,
        url: str,
        api_key: Optional[str],
        collection: str,
        vector_size: int,
        distance: str,
    ) -> None:
        self._collection = collection
        self._vector_size = vector_size
        self._distance = self._parse_distance(distance)
        self._client = QdrantClient(url=url, api_key=api_key)
        # Memoize collection/index existence so hot paths (search/upsert) don't
        # round-trip a collection_exists()/create_payload_index() check every call.
        self._collection_ready = False
        self._text_index_ready = False

    def _resolve_point_id(self, document: StoredDocument) -> Union[str, int]:
        doc_id = document.id
        if doc_id is None:
            return uuid4().hex
        if isinstance(doc_id, int):
            if doc_id < 0:
                logger.warning("Negative document id %s is not supported; generating a UUID instead", doc_id)
                return uuid4().hex
            return doc_id
        raw = str(doc_id).strip()
        if raw.isdigit():
            return int(raw)
        try:
            return str(UUID(raw))
        except ValueError:
            logger.warning("Invalid document id '%s'; generating a UUID instead", raw)
            return uuid4().hex

    @staticmethod
    def _parse_distance(value: str) -> Distance:
        normalized = value.strip().upper()
        if normalized in {"COSINE", "COS"}:
            return Distance.COSINE
        if normalized in {"EUCLID", "L2", "EUCLIDEAN"}:
            return Distance.EUCLID
        if normalized in {"DOT", "DOTPRODUCT"}:
            return Distance.DOT
        raise ValueError(f"Unsupported distance metric: {value}")

    @property
    def collection(self) -> str:
        return self._collection

    def ensure_collection(self) -> None:
        """Create the collection if it is missing. Memoized after the first check."""

        if self._collection_ready:
            return

        if self._client.collection_exists(self._collection):
            self._collection_ready = True
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=self._vector_size, distance=self._distance),
        )
        self._collection_ready = True

    def ensure_text_payload_index(self) -> None:
        """
        Ensure payload full-text index on `text` for keyword/hybrid recall.

        Memoized per instance: the underlying create_payload_index() call is a
        write operation, so without this flag it would run on every search/upsert.
        """
        if self._text_index_ready:
            return
        self.ensure_collection()
        try:
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name="text",
                field_schema=PayloadSchemaType.TEXT,
            )
        except Exception:
            # Index may already exist; Qdrant raises on duplicate. Either way,
            # don't keep retrying this on every call.
            logger.debug("text payload index ensure skipped/failed for %s", self._collection, exc_info=True)
        self._text_index_ready = True

    def upsert(
        self,
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[StoredDocument],
        *,
        user_id: str,
    ) -> List[str]:
        """Upsert document chunks and their embeddings into Qdrant for one user."""

        if len(embeddings) != len(documents):
            raise ValueError("Embeddings and documents collections must have the same length")

        points: List[PointStruct] = []
        point_ids: List[str] = []
        for vector, document in zip(embeddings, documents):
            payload = {**document.metadata, "text": document.text, USER_ID_PAYLOAD_KEY: user_id}
            point_id = self._resolve_point_id(document)
            point_ids.append(str(point_id))
            points.append(PointStruct(id=point_id, vector=list(vector), payload=payload))

        if points:
            self.ensure_collection()
            self._client.upsert(collection_name=self._collection, points=points)
            try:
                self.ensure_text_payload_index()
            except Exception:
                logger.debug("payload index ensure after upsert failed", exc_info=True)
        return point_ids

    def _user_filter(self, user_id: str) -> Filter:
        return Filter(
            must=[
                FieldCondition(
                    key=USER_ID_PAYLOAD_KEY,
                    match=MatchValue(value=user_id),
                )
            ]
        )

    def delete_for_user(self, user_id: str) -> None:
        """Delete all vector points belonging to one user."""
        if not self._client.collection_exists(self._collection):
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(filter=self._user_filter(user_id)),
        )

    def keyword_search(
        self,
        query: str,
        *,
        user_id: str,
        limit: int,
    ) -> List[Any]:
        """
        Sparse/keyword recall via Qdrant full-text MatchText on payload `text`.

        Returns unscored scroll hits (score may be absent); callers should assign
        lexical scores when merging with dense results. Runs as a single scroll
        with an OR (`should`) filter across the significant query terms, rather
        than one round-trip per term.
        """
        terms = significant_query_terms(query)
        if not terms or limit <= 0:
            return []

        self.ensure_text_payload_index()
        query_filter = Filter(
            must=[FieldCondition(key=USER_ID_PAYLOAD_KEY, match=MatchValue(value=user_id))],
            should=[FieldCondition(key="text", match=MatchText(text=term)) for term in terms],
        )
        try:
            points, _next = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=query_filter,
                limit=max(limit * 3, 12),
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            logger.warning("keyword scroll failed for terms=%r", terms, exc_info=True)
            return []

        hits_by_id: Dict[str, Any] = {str(point.id): point for point in points or []}
        return list(hits_by_id.values())[: max(limit * 2, limit)]

    def search(
        self,
        query_vector: Sequence[float],
        *,
        user_id: str,
        limit: int,
        score_threshold: Optional[float] = None,
        query_text: Optional[str] = None,
        hybrid: bool = False,
    ) -> List[Any]:
        """Return Qdrant search results scoped to a single user.

        When hybrid=True and query_text is provided, merge dense ANN hits with
        keyword/MatchText recall so terms the embedder misses still enter rerank.
        """

        self.ensure_collection()
        dense_hits = self._client.search(
            collection_name=self._collection,
            query_vector=list(query_vector),
            limit=limit,
            score_threshold=score_threshold,
            query_filter=self._user_filter(user_id),
            with_payload=True,
        )
        if not hybrid or not query_text:
            return dense_hits

        keyword_hits = self.keyword_search(query_text, user_id=user_id, limit=limit)
        return merge_dense_and_keyword_hits(
            query=query_text,
            dense_hits=dense_hits,
            keyword_hits=keyword_hits,
        )


__all__ = ["VectorStore", "StoredDocument", "USER_ID_PAYLOAD_KEY"]
