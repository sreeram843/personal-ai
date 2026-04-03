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
from app.services.live_data_manager import LiveDataManager
from app.services.ollama import OllamaClient
from app.services.plan_linter import PlanLinter
from app.services.run_store import RunStore
from app.services.tool_registry import ToolRegistry
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.workflow_memory import WorkflowMemoryStore


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


@lru_cache
def get_workflow_memory_store() -> WorkflowMemoryStore:
    settings = get_settings()
    return WorkflowMemoryStore(
        file_path=settings.workflow_memory_path,
        max_entries_per_conversation=settings.workflow_memory_max_entries,
    )


@lru_cache
def get_llm_gateway() -> LLMGateway:
    settings = get_settings()
    adapters = {
        "ollama": OllamaLLMAdapter(get_ollama_client()),
    }
    if settings.llm_openai_base_url:
        adapters["openai"] = OpenAICompatibleLLMAdapter(
            base_url=settings.llm_openai_base_url,
            api_key=settings.llm_openai_api_key,
            timeout=settings.llm_openai_timeout,
        )
    return LLMGateway(adapters=adapters, default_provider=settings.llm_default_provider)


@lru_cache
def get_workflow_model_profile() -> WorkflowModelProfile:
    settings = get_settings()
    return WorkflowModelProfile(
        planner=StageModelConfig(provider=settings.llm_planner_provider, model=settings.llm_planner_model),
        synthesizer=StageModelConfig(provider=settings.llm_synthesizer_provider, model=settings.llm_synthesizer_model),
        reviewer=StageModelConfig(provider=settings.llm_reviewer_provider, model=settings.llm_reviewer_model),
        writer=StageModelConfig(provider=settings.llm_writer_provider, model=settings.llm_writer_model),
    )


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Return singleton tool registry instance."""
    return ToolRegistry()


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
    return RunStore(storage_path=settings.workflow_runs_path)


__all__ = [
    "get_vector_store",
    "get_ollama_client",
    "get_web_search",
    "get_live_data_manager",
    "get_workflow_memory_store",
    "get_llm_gateway",
    "get_workflow_model_profile",
    "get_tool_registry",
    "get_plan_linter",
    "get_fallback_plan_manager",
    "get_run_store",
]
