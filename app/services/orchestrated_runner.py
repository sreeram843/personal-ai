from __future__ import annotations

from typing import Literal

from app.core.config import get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_messages import get_last_user_message
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.ollama import OllamaClient
from app.services.orchestrated_chat import OrchestratedChatService
from app.services.prompt_context import augment_system_prompt
from app.services.system_prompt import get_system_prompt
from app.services.tool_registry import ToolRegistry
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.workflow_memory import WorkflowMemoryStore


def merge_workflow_options(payload: ChatRequest):
    merged = dict(payload.options or {})
    workflow = payload.workflow
    if not workflow:
        return merged
    merged.setdefault("reviewer_quorum", workflow.reviewer_quorum)
    merged.setdefault("require_evidence_markers", workflow.require_evidence_markers)
    merged.setdefault("trust_lanes_enabled", workflow.trust_lanes_enabled)
    merged.setdefault("token_budget", workflow.token_budget)
    merged.setdefault("progressive_disclosure_level", workflow.progressive_disclosure_level)
    return merged


def build_orchestrated_service(
    *,
    ollama: OllamaClient,
    llm_gateway: LLMGateway,
    model_profile: WorkflowModelProfile,
    web_search: WebSearchService,
    vector_store: VectorStore,
    workflow_memory: WorkflowMemoryStore,
) -> OrchestratedChatService:
    return OrchestratedChatService(
        embed_client=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        memory_store=workflow_memory,
    )


async def run_orchestrated_mode(
    *,
    mode: Literal["chat", "rag", "workflow"],
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
    if mode == "chat":
        from app.services.chat_execution import execute_chat_mode

        return await execute_chat_mode(
            payload=payload,
            user_id=user_id,
            ollama=ollama,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
            vector_store=vector_store,
            web_search=web_search,
            workflow_memory=workflow_memory,
            tool_registry=tool_registry,
        )

    service = build_orchestrated_service(
        ollama=ollama,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
        web_search=web_search,
        vector_store=vector_store,
        workflow_memory=workflow_memory,
    )
    workflow = payload.workflow
    settings = get_settings()
    query = get_last_user_message(payload).content
    from app.core.deps import get_skill_catalog, get_user_memory_store
    from app.services.skill_resolution import resolve_skill_for_request

    skill_match = resolve_skill_for_request(
        get_skill_catalog(),
        user_id=user_id,
        payload=payload,
    )
    system_prompt = augment_system_prompt(
        get_system_prompt(),
        user_query=query,
        user_id=user_id,
        settings=settings,
        user_memory_store=get_user_memory_store(),
        skill_addendum=skill_match.skill.system_addendum if skill_match else None,
        skill_name=skill_match.skill.name if skill_match else None,
    )
    response = await service.run_mode(
        mode=mode,
        query=query,
        system_prompt=system_prompt,
        chat_history=[{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]],
        conversation_id=payload.conversation_id,
        user_id=user_id,
        top_k=payload.top_k or settings.default_top_k,
        score_threshold=payload.score_threshold,
        options=merge_workflow_options(payload),
        use_rag=workflow.use_rag if workflow else mode != "chat",
        include_trace=workflow.include_trace if workflow else mode == "workflow",
        persist_memory=workflow.persist_memory if workflow else mode == "workflow",
        max_steps=workflow.max_steps if workflow else 6,
    )
    _record_orchestrated_consolidation(
        user_id=user_id,
        user_message=query,
        assistant_message=response.message,
        workflow_status=response.workflow.status if response.workflow else None,
    )
    return response


def _record_orchestrated_consolidation(
    *,
    user_id: str,
    user_message: str,
    assistant_message: str,
    workflow_status: str | None,
) -> None:
    settings = get_settings()
    if not settings.enable_memory_consolidation or not user_id:
        return
    if workflow_status == "failed":
        return
    from app.core.deps import get_memory_consolidation_service

    get_memory_consolidation_service().record_turn(
        user_id,
        user_message=user_message,
        assistant_message=assistant_message,
    )
