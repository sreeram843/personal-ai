from functools import lru_cache

from app.core.config import get_settings
from app.services.ollama import OllamaClient
from app.services.vector_store import VectorStore


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    store = VectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection,
        vector_size=settings.embedding_dimension,
        distance=settings.qdrant_distance,
    )
    store.ensure_collection()
    return store


@lru_cache
def get_ollama_client() -> OllamaClient:
    settings = get_settings()
    return OllamaClient(
        base_url=settings.ollama_base_url,
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
        timeout=settings.ollama_timeout,
    )


__all__ = ["get_vector_store", "get_ollama_client"]
