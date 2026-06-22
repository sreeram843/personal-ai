"""Tests for per-user Qdrant payload scoping."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.vector_store import StoredDocument, VectorStore


def test_upsert_adds_user_id_to_payload() -> None:
    client = MagicMock()
    client.collection_exists.return_value = True
    store = VectorStore(
        url="http://127.0.0.1:6333",
        api_key=None,
        collection="test",
        vector_size=3,
        distance="Cosine",
    )
    store._client = client

    point_ids = store.upsert(
        [[0.1, 0.2, 0.3]],
        [StoredDocument(text="hello", metadata={"path": "docs/a.md"})],
        user_id="user-a",
    )

    assert len(point_ids) == 1
    client.upsert.assert_called_once()
    points = client.upsert.call_args.kwargs["points"]
    assert points[0].payload["user_id"] == "user-a"
    assert points[0].payload["text"] == "hello"


def test_search_applies_user_filter() -> None:
    client = MagicMock()
    client.collection_exists.return_value = True
    client.search.return_value = []
    store = VectorStore(
        url="http://127.0.0.1:6333",
        api_key=None,
        collection="test",
        vector_size=3,
        distance="Cosine",
    )
    store._client = client

    store.search([0.1, 0.2, 0.3], user_id="user-b", limit=4)

    client.search.assert_called_once()
    assert client.search.call_args.kwargs["query_filter"] is not None
    assert client.search.call_args.kwargs["query_filter"].model_dump()["must"][0]["key"] == "user_id"


def test_search_ensures_collection_before_query() -> None:
    client = MagicMock()
    client.collection_exists.return_value = False
    client.search.return_value = []
    store = VectorStore(
        url="http://127.0.0.1:6333",
        api_key=None,
        collection="test",
        vector_size=3,
        distance="Cosine",
    )
    store._client = client

    store.search([0.1, 0.2, 0.3], user_id="user-b", limit=4)

    client.create_collection.assert_called_once()
    client.search.assert_called_once()
