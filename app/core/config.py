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

    llm_default_provider: str = "ollama"
    llm_default_model: str = "llama3:8b"
    llm_openai_base_url: Optional[str] = None
    llm_openai_api_key: Optional[str] = None
    llm_openai_timeout: float = 60.0
    llm_planner_provider: str = "ollama"
    llm_planner_model: str = "qwen2.5:3b"
    llm_synthesizer_provider: str = "ollama"
    llm_synthesizer_model: str = "qwen2.5:7b"
    llm_reviewer_provider: str = "ollama"
    llm_reviewer_model: str = "qwen2.5:3b"
    llm_writer_provider: str = "ollama"
    llm_writer_model: str = "llama3:8b"

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

    workflow_memory_path: str = "memory/workflow_sessions.json"
    workflow_memory_max_entries: int = 24
    workflow_runs_path: str = "memory/runs"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
