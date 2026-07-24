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


def test_ensure_collection_and_text_index_are_memoized() -> None:
    """
    collection_exists()/create_payload_index() are write-adjacent round-trips;
    they should run at most once per VectorStore instance, not once per search.
    """
    client = MagicMock()
    client.collection_exists.return_value = True
    client.search.return_value = []
    client.scroll.return_value = ([], None)
    store = VectorStore(
        url="http://127.0.0.1:6333",
        api_key=None,
        collection="test",
        vector_size=3,
        distance="Cosine",
    )
    store._client = client

    for _ in range(3):
        store.search([0.1, 0.2, 0.3], user_id="user-b", limit=4, query_text="hello world", hybrid=True)

    assert client.collection_exists.call_count == 1
    assert client.create_payload_index.call_count == 1


def test_keyword_search_uses_a_single_scroll_call() -> None:
    """Keyword recall across multiple significant terms should be one OR'd
    scroll() call, not one round-trip per term."""
    client = MagicMock()
    client.collection_exists.return_value = True
    client.scroll.return_value = ([], None)
    store = VectorStore(
        url="http://127.0.0.1:6333",
        api_key=None,
        collection="test",
        vector_size=3,
        distance="Cosine",
    )
    store._client = client

    store.keyword_search("kubernetes rollout deployment strategy", user_id="user-c", limit=4)

    client.scroll.assert_called_once()
    query_filter = client.scroll.call_args.kwargs["scroll_filter"].model_dump()
    assert query_filter["must"][0]["key"] == "user_id"
    assert len(query_filter["should"]) >= 2
