"""Chat-mode execution strategies: fast single-call, tool agent, or full orchestration."""

from __future__ import annotations

from typing import Literal

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.fast_chat import run_fast_chat
from app.services.information_routing import is_trivial_chitchat
from app.services.langchain_agent import run_langchain_agent
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.ollama import OllamaClient
from app.services.chat_messages import get_last_user_message
from app.services.system_prompt import get_system_prompt
from app.services.tool_registry import ToolRegistry
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.workflow_memory import WorkflowMemoryStore

ChatExecutionStrategy = Literal["fast", "tools", "orchestrated"]


def resolve_chat_execution_strategy(query: str, settings: Settings | None = None) -> ChatExecutionStrategy:
    """Pick the cheapest path that can answer the user well."""
    cfg = settings or get_settings()
    if cfg.enable_fast_chat and is_trivial_chitchat(query):
        return "fast"
    if cfg.enable_langchain_agent:
        return "tools"
    return "orchestrated"


async def execute_chat_mode(
    *,
    payload: ChatRequest,
    user_id: str,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    vector_store: VectorStore,
    web_search: WebSearchService,
    workflow_memory: WorkflowMemoryStore,
    tool_registry: ToolRegistry,
) -> ChatResponse:
    """Run /chat or Smart 'chat' tier with fast, tool-agent, or orchestrated fallback."""
    settings = get_settings()
    query = get_last_user_message(payload).content
    history = [{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]]
    strategy = resolve_chat_execution_strategy(query, settings)

    if strategy == "fast":
        return await run_fast_chat(
            query=query,
            chat_history=history,
            llm_gateway=llm_gateway,
            settings=settings,
        )

    if strategy == "tools":
        try:
            text = await run_langchain_agent(
                query=query,
                system_prompt=get_system_prompt(),
                chat_history=history,
                tool_registry=tool_registry,
                settings=settings,
            )
            return ChatResponse(message=text, sources=[])
        except Exception:
            # Cloud providers may reject tool-calling or LangChain wiring can fail;
            # fall back to a single LLM call instead of returning HTTP 500 to the UI.
            return await run_fast_chat(
                query=query,
                chat_history=history,
                llm_gateway=llm_gateway,
                settings=settings,
            )

    # Legacy multi-agent chat pipeline (researcher → synthesizer → reviewer → writer).
    from app.services.orchestrated_runner import build_orchestrated_service, merge_workflow_options

    service = build_orchestrated_service(
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        workflow_memory=workflow_memory,
    )
    workflow = payload.workflow
    return await service.run_mode(
        mode="chat",
        query=query,
        system_prompt=get_system_prompt(),
        chat_history=history,
        conversation_id=payload.conversation_id,
        user_id=user_id,
        top_k=payload.top_k or settings.default_top_k,
        score_threshold=payload.score_threshold,
        options=merge_workflow_options(payload),
        use_rag=workflow.use_rag if workflow else False,
        include_trace=workflow.include_trace if workflow else False,
        persist_memory=workflow.persist_memory if workflow else False,
        max_steps=workflow.max_steps if workflow else 6,
    )


__all__ = [
    "ChatExecutionStrategy",
    "execute_chat_mode",
    "resolve_chat_execution_strategy",
]
