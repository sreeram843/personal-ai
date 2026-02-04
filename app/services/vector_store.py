from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


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
        """Create the collection if it is missing."""

        if self._client.collection_exists(self._collection):
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=self._vector_size, distance=self._distance),
        )

    def upsert(self, embeddings: Sequence[Sequence[float]], documents: Sequence[StoredDocument]) -> None:
        """Upsert document chunks and their embeddings into Qdrant."""

        if len(embeddings) != len(documents):
            raise ValueError("Embeddings and documents collections must have the same length")

        points = []
        for vector, document in zip(embeddings, documents):
            payload = {**document.metadata, "text": document.text}
            point_id = self._resolve_point_id(document)
            points.append(PointStruct(id=point_id, vector=list(vector), payload=payload))

        if points:
            self._client.upsert(collection_name=self._collection, points=points)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int,
        score_threshold: Optional[float] = None,
    ) -> List[Any]:
        """Return the raw Qdrant search results."""

        return self._client.search(
            collection_name=self._collection,
            query_vector=list(query_vector),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )


__all__ = ["VectorStore", "StoredDocument"]
