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

    enable_fast_chat: bool = True
    enable_langchain_agent: bool = True
    enable_llamaindex_rag: bool = False

    enable_adapter_cache: bool = True
    adapter_cache_backend: str = "memory"
    adapter_cache_default_ttl_seconds: int = 60
    live_cache_ttl_fx_seconds: int = 60
    live_cache_ttl_stock_seconds: int = 30
    live_cache_ttl_commodity_seconds: int = 30
    live_cache_ttl_weather_current_seconds: int = 300
    live_cache_ttl_weather_forecast_seconds: int = 900
    live_cache_ttl_news_seconds: int = 180
    geocoding_cache_ttl_seconds: int = 86_400
    market_data_provider: str = "yahoo"
    finnhub_api_key: Optional[str] = None
    redis_url: Optional[str] = None

    enable_background_workers: bool = False
    worker_queue_backend: str = "arq"
    ingest_async_min_documents: int = 5
    ingest_async_min_bytes: int = 32768

    workflow_memory_path: str = "memory/workflow_sessions.json"
    workflow_memory_max_entries: int = 24
    workflow_memory_backend: str = "disk"
    workflow_runs_path: str = "memory/runs"
    run_store_backend: str = "disk"

    object_storage_backend: str = "local"
    object_storage_local_path: str = "memory/uploads"
    object_storage_bucket: Optional[str] = None
    object_storage_prefix: str = "uploads"
    object_storage_endpoint_url: Optional[str] = None
    object_storage_region: Optional[str] = None
    object_storage_access_key: Optional[str] = None
    object_storage_secret_key: Optional[str] = None

    # PostgreSQL (Phase 1 multi-user persistence)
    database_url: str = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/personal_ai"

    # Authentication (Phase 1)
    auth_disabled: bool = True
    jwt_secret: str = "dev-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    dev_user_email: str = "dev@localhost"
    dev_user_display_name: str = "Dev User"
    google_client_id: Optional[str] = None

    # Public portfolio demo (embeddable /demo UI, no auth)
    demo_enabled: bool = False
    demo_max_questions: int = 5
    demo_intro: Optional[str] = None
    demo_full_app_url: Optional[str] = None
    demo_embed_allowed_origins: str = ""
    demo_context_path: Optional[str] = None
    # Keep demo prompts small enough for local LM Studio / 4k context windows.
    demo_context_max_chars: int = 8500
    demo_max_history_messages: int = 6
    demo_max_output_tokens: int = 512

    # Path to assistant system prompt markdown (default: app/prompts/system.md)
    system_prompt_path: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
