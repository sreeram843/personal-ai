from functools import lru_cache

from app.core.config import get_settings
from app.services.adapter_cache import build_adapter_cache
from app.services.live_data_manager import LiveDataManager
from app.services.ollama import OllamaClient
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService


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


@lru_cache
def get_web_search() -> WebSearchService:
    return WebSearchService(max_results=5, timeout=10)


@lru_cache
def get_live_data_manager() -> LiveDataManager:
    settings = get_settings()
    cache = build_adapter_cache(settings)
    return LiveDataManager(web_search=get_web_search(), cache=cache, settings=settings)


__all__ = ["get_vector_store", "get_ollama_client", "get_web_search", "get_live_data_manager"]
