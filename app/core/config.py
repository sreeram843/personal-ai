from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field
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
    retrieval_wide_top_k: int = 20
    retrieval_rerank_enabled: bool = True
    retrieval_query_decomposition_enabled: bool = True
    retrieval_query_decomposition_max_queries: int = 3
    retrieval_query_decomposition_min_words: int = 4
    enable_document_summary_index: bool = True
    document_summary_max_chars: int = 600
    document_summary_max_input_chars: int = 12000
    document_summary_provider: str = "ollama"
    document_summary_model: str = "qwen2.5:3b"
    retrieval_summary_boost: float = 0.12
    enable_self_rag_retry: bool = True
    self_rag_max_hops: int = 2
    self_rag_min_top_score: float = 0.42
    self_rag_min_lexical_overlap: float = 0.15
    self_rag_use_llm_judge: bool = True
    enable_context_compression: bool = True
    context_compression_target_ratio: float = 0.5
    context_compression_block_max_chars: int = 1200
    context_compression_min_chars: int = 400
    context_compression_use_llmlingua: bool = False
    enable_corpus_synthesis: bool = True
    corpus_synthesis_max_documents: int = 6
    corpus_synthesis_include_supporting_chunks: bool = True
    corpus_synthesis_graph_boost: float = 0.10
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"

    enable_fast_chat: bool = True
    # When no other tier matches, use fast for local MLX/LM Studio; orchestrated for cloud/GPU.
    chat_fallback_strategy: str = "orchestrated"
    enable_tool_agent: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "enable_tool_agent",
            "enable_langchain_agent",
            "ENABLE_TOOL_AGENT",
            "ENABLE_LANGCHAIN_AGENT",
        ),
    )
    enable_openai_api: bool = True
    enable_llamaindex_rag: bool = True
    llamaindex_sentence_window_size: int = 3

    enable_adapter_cache: bool = True
    adapter_cache_backend: str = "memory"
    adapter_cache_default_ttl_seconds: int = 60
    live_cache_ttl_fx_seconds: int = 60
    live_cache_ttl_stock_seconds: int = 30
    live_cache_ttl_commodity_seconds: int = 30
    live_cache_ttl_weather_current_seconds: int = 300
    live_cache_ttl_weather_forecast_seconds: int = 900
    live_cache_ttl_news_seconds: int = 180
    live_cache_ttl_sports_seconds: int = 30
    live_cache_ttl_nearby_places_seconds: int = 3600
    enable_nearby_places_llm_clarification: bool = True
    geocoding_cache_ttl_seconds: int = 86_400
    market_data_provider: str = "yahoo"
    finnhub_api_key: Optional[str] = None
    redis_url: Optional[str] = None

    # Web connectors (Tavily / Perplexity search, Firecrawl scrape)
    web_search_provider: str = "auto"
    tavily_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    firecrawl_api_key: Optional[str] = None

    enable_background_workers: bool = False
    worker_queue_backend: str = "arq"
    ingest_async_min_documents: int = 5
    ingest_async_min_bytes: int = 32768
    # Reject oversized / disallowed ingest payloads (JSON /ingest).
    ingest_max_document_bytes: int = 512_000
    ingest_max_batch_bytes: int = 2_000_000
    ingest_allowed_extensions: str = ".txt,.md"

    # Optional public legal URLs (OAuth consent + login footer).
    privacy_policy_url: Optional[str] = None
    terms_of_service_url: Optional[str] = None

    workflow_memory_path: str = "memory/workflow_sessions.json"
    workflow_memory_max_entries: int = 24
    workflow_memory_backend: str = "disk"
    user_memory_path: str = "memory/user_summaries.json"
    user_memory_max_entries: int = 12
    enable_user_memory: bool = True
    enable_llm_history_compaction: bool = True
    enable_runtime_mcp: bool = True
    mcp_servers_path: str = "memory/mcp_servers.json"
    mcp_connect_timeout: float = 20.0
    bundled_skills_path: str = "skills"
    user_skills_path: str = "memory/user_skills.json"
    agent_tasks_path: str = "memory/agent_tasks.json"
    agent_tasks_max_per_user: int = 40
    enable_sentiment_tone: bool = True
    calendar_ics_url: Optional[str] = None
    scheduled_reports_path: str = "memory/scheduled_reports.json"
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
    # Comma-separated emails promoted to admin on login/bootstrap
    admin_emails: str = ""
    # invite | open — open allows Google auto-create without invite
    auth_signup_mode: str = "invite"
    # Fernet master key for encrypting provider API keys in DB (required in prod)
    settings_secret_key: Optional[str] = None

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

    # Fast chat context compaction (rolling summary + recent turns)
    chat_history_compact_after: int = 6
    chat_history_recent_messages: int = 4
    chat_history_summary_max_chars: int = 800

    # Path to assistant system prompt markdown (default: app/prompts/system.md)
    system_prompt_path: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
