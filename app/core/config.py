from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "personal-ai"
    debug: bool = False

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "llama3:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: float = 120.0

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "personal_ai_documents"
    qdrant_distance: str = "Cosine"
    embedding_dimension: int = 768
    default_top_k: int = 4
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"

    enable_langchain_agent: bool = False
    enable_llamaindex_rag: bool = False

    enable_adapter_cache: bool = True
    adapter_cache_backend: str = "memory"
    adapter_cache_default_ttl_seconds: int = 60
    redis_url: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
