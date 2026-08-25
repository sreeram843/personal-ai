from functools import lru_cache

from app.core.config import get_settings
from app.services.adapter_cache import build_adapter_cache
from app.services.fallback_plan_manager import FallbackPlanManager
from app.services.llm_gateway import (
    LLMGateway,
    OllamaLLMAdapter,
    OpenAICompatibleLLMAdapter,
    StageModelConfig,
    WorkflowModelProfile,
)
from app.services.geocoding import GeocodingService
from app.services.live_data_manager import LiveDataManager
from app.services.market_data import build_market_data_provider
from app.services.ollama import OllamaClient
from app.services.plan_linter import PlanLinter
from app.services.object_storage import ObjectStorage, build_object_storage
from app.services.run_store import RunStore, build_run_store
from app.services.tool_registry import ToolRegistry
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.workflow_memory import WorkflowMemoryStore, build_workflow_memory_store
from app.services.user_memory import UserMemoryStore, build_user_memory_store
from app.services.memory_consolidation import (
    MemoryConsolidationService,
    build_memory_consolidation_service,
)
from app.services.schedule_store import ScheduleStore, build_schedule_store
from app.services.mcp_store import McpServerStore, build_mcp_server_store
from app.services.skill_loader import SkillCatalog, SkillStore, build_skill_catalog, build_skill_store
from app.services.skill_implicit import SkillImplicitStore, build_skill_implicit_store
from app.services.agent_task_store import AgentTaskStore, build_agent_task_store
from app.services.job_store import JobStore
from app.db.session import get_db


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
    settings = get_settings()
    cache = build_adapter_cache(settings) if settings.enable_adapter_cache else None
    geocoder = GeocodingService(
        timeout=settings.llm_openai_timeout,
        cache=cache,
        cache_ttl_seconds=settings.geocoding_cache_ttl_seconds,
    )
    market_data = build_market_data_provider(
        provider=settings.market_data_provider,
        api_key=settings.finnhub_api_key,
    )
    return WebSearchService(
        max_results=5,
        timeout=10,
        geocoder=geocoder,
        market_data=market_data,
        settings=settings,
    )


@lru_cache
def get_live_data_manager() -> LiveDataManager:
    settings = get_settings()
    cache = build_adapter_cache(settings)
    return LiveDataManager(web_search=get_web_search(), cache=cache, settings=settings)


@lru_cache
def get_workflow_memory_store() -> WorkflowMemoryStore:
    settings = get_settings()
    return build_workflow_memory_store(
        file_path=settings.workflow_memory_path,
        max_entries=settings.workflow_memory_max_entries,
        backend=settings.workflow_memory_backend,
        redis_url=settings.redis_url,
    )


@lru_cache
def get_user_memory_store() -> UserMemoryStore:
    settings = get_settings()
    return build_user_memory_store(
        file_path=settings.user_memory_path,
        max_entries=settings.user_memory_max_entries,
    )


@lru_cache
def get_memory_consolidation_service() -> MemoryConsolidationService:
    settings = get_settings()
    return build_memory_consolidation_service(file_path=settings.memory_consolidation_path)


@lru_cache
def get_schedule_store() -> ScheduleStore:
    settings = get_settings()
    return build_schedule_store(file_path=settings.scheduled_reports_path)


@lru_cache
def get_mcp_server_store() -> McpServerStore:
    settings = get_settings()
    return build_mcp_server_store(file_path=settings.mcp_servers_path)


@lru_cache
def get_skill_store() -> SkillStore:
    settings = get_settings()
    return build_skill_store(file_path=settings.user_skills_path)


@lru_cache
def get_skill_implicit_store() -> SkillImplicitStore:
    settings = get_settings()
    return build_skill_implicit_store(file_path=settings.skill_implicit_path)


@lru_cache
def get_skill_catalog() -> SkillCatalog:
    settings = get_settings()
    return build_skill_catalog(
        bundled_root=settings.bundled_skills_path,
        store=get_skill_store(),
        implicit=get_skill_implicit_store(),
    )


@lru_cache
def get_agent_task_store() -> AgentTaskStore:
    settings = get_settings()
    return build_agent_task_store(
        file_path=settings.agent_tasks_path,
        max_tasks_per_user=settings.agent_tasks_max_per_user,
    )


@lru_cache
def get_llm_gateway() -> LLMGateway:
    """Build the LLM gateway with one adapter per enabled admin provider.

    Each `llm_providers` row becomes its own OpenAI-compatible adapter keyed by
    provider name, so stage routing can mix Groq / OpenAI / DeepSeek / etc.
    Env `LLM_OPENAI_*` remains registered as `openai` when not overridden in DB.
    """
    settings = get_settings()
    adapters = {
        "ollama": OllamaLLMAdapter(get_ollama_client()),
    }
    default_provider = settings.llm_default_provider
    db_providers = []
    try:
        from app.db.session import get_session_factory
        from app.services.settings_store import get_effective_routing, list_enabled_provider_configs

        db = get_session_factory()()
        try:
            routing = get_effective_routing(db, settings)
            default_provider = routing.default_provider
            db_providers = list_enabled_provider_configs(db, settings)
        finally:
            db.close()
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Failed to load admin LLM providers; falling back to Ollama-only gateway"
        )

    for provider in db_providers:
        if not provider.base_url:
            continue
        adapters[provider.provider_name] = OpenAICompatibleLLMAdapter(
            base_url=provider.base_url,
            api_key=provider.api_key,
            timeout=settings.llm_openai_timeout,
        )

    # Env bootstrap / fallback under the historical "openai" provider key.
    if settings.llm_openai_base_url and "openai" not in adapters:
        adapters["openai"] = OpenAICompatibleLLMAdapter(
            base_url=settings.llm_openai_base_url,
            api_key=settings.llm_openai_api_key,
            timeout=settings.llm_openai_timeout,
        )

    if default_provider not in adapters:
        if "openai" in adapters:
            adapters[default_provider] = adapters["openai"]
        elif db_providers:
            first_name = db_providers[0].provider_name
            if first_name in adapters:
                adapters[default_provider] = adapters[first_name]

    return LLMGateway(adapters=adapters, default_provider=default_provider)


@lru_cache
def get_workflow_model_profile() -> WorkflowModelProfile:
    settings = get_settings()
    try:
        from app.db.session import get_session_factory
        from app.services.settings_store import get_effective_routing

        db = get_session_factory()()
        try:
            routing = get_effective_routing(db, settings)
            return WorkflowModelProfile(
                planner=StageModelConfig(provider=routing.planner_provider, model=routing.planner_model),
                synthesizer=StageModelConfig(
                    provider=routing.synthesizer_provider, model=routing.synthesizer_model
                ),
                reviewer=StageModelConfig(provider=routing.reviewer_provider, model=routing.reviewer_model),
                writer=StageModelConfig(provider=routing.writer_provider, model=routing.writer_model),
            )
        finally:
            db.close()
    except Exception:
        pass
    return WorkflowModelProfile(
        planner=StageModelConfig(provider=settings.llm_planner_provider, model=settings.llm_planner_model),
        synthesizer=StageModelConfig(provider=settings.llm_synthesizer_provider, model=settings.llm_synthesizer_model),
        reviewer=StageModelConfig(provider=settings.llm_reviewer_provider, model=settings.llm_reviewer_model),
        writer=StageModelConfig(provider=settings.llm_writer_provider, model=settings.llm_writer_model),
    )


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Return singleton tool registry with built-in tools registered."""
    from app.services.builtin_tools import register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(
        registry,
        get_web_search(),
        live_data=get_live_data_manager(),
        ollama=get_ollama_client(),
        vector_store=get_vector_store(),
        settings=get_settings(),
        llm_gateway=get_llm_gateway(),
        model_profile=get_workflow_model_profile(),
    )
    return registry


@lru_cache
def get_plan_linter() -> PlanLinter:
    """Return singleton plan linter instance."""
    return PlanLinter()


@lru_cache
def get_fallback_plan_manager() -> FallbackPlanManager:
    """Return singleton fallback plan manager instance."""
    return FallbackPlanManager()


@lru_cache
def get_run_store() -> RunStore:
    """Return singleton run store instance."""
    settings = get_settings()
    return build_run_store(
        storage_path=settings.workflow_runs_path,
        backend=settings.run_store_backend,
        redis_url=settings.redis_url,
    )


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    return build_object_storage(settings)


@lru_cache
def get_job_store() -> JobStore:
    settings = get_settings()
    return JobStore(redis_url=settings.redis_url)


__all__ = [
    "get_vector_store",
    "get_ollama_client",
    "get_web_search",
    "get_live_data_manager",
    "get_workflow_memory_store",
    "get_user_memory_store",
    "get_memory_consolidation_service",
    "get_schedule_store",
    "get_mcp_server_store",
    "get_skill_store",
    "get_skill_catalog",
    "get_agent_task_store",
    "get_llm_gateway",
    "get_workflow_model_profile",
    "get_tool_registry",
    "get_plan_linter",
    "get_fallback_plan_manager",
    "get_run_store",
    "get_object_storage",
    "get_job_store",
    "get_db",
]
