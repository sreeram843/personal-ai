"""Chat-mode execution strategies: fast single-call, tool agent, or full orchestration."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal, Optional

from app.core.config import Settings, get_settings
from app.core.deps import get_mcp_server_store
from app.schemas.agent import ChatAgentOptions
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.fast_chat import run_fast_chat
from app.services.information_routing import (
    is_document_grounded_query,
    is_simple_direct_chat,
    is_trivial_chitchat,
    prefers_tool_agent_for_query,
    should_route_chat_toward_tools,
)
from app.services.tool_agent import run_tool_agent
from app.services.live_block_collector import get_live_blocks, reset_live_blocks, restore_live_blocks
from app.services.live_block_events import (
    activate_block_event_callbacks,
    deactivate_block_event_callbacks,
)
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.mcp_tools import discover_user_mcp_tools
from app.services.ollama import OllamaClient
from app.services.chat_messages import get_last_user_message
from app.services.prompt_context import augment_system_prompt
from app.services.sentiment_routing import detect_sentiment
from app.services.skill_context import activate_skill_context, deactivate_skill_context
from app.services.skill_resolution import resolve_skill_for_request
from app.services.system_prompt import get_system_prompt
from app.services.tool_permissions import (
    activate_tool_execution_context,
    deactivate_tool_execution_context,
    get_tool_execution_context,
)
from app.services.tool_registry import ToolRegistry
from app.services.user_memory import extract_memory_facts_heuristic
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService
from app.services.workflow_memory import WorkflowMemoryStore

ChatExecutionStrategy = Literal["fast", "tools", "orchestrated"]


def resolve_chat_execution_strategy(
    query: str,
    settings: Settings | None = None,
    options: dict | None = None,
) -> ChatExecutionStrategy:
    """Pick the cheapest Chat path: fast single-call or tools.

    Multi-agent orchestration is reserved for Smart /workflow_chat — Chat mode
    must not escalate into planner/synthesizer/reviewer/writer by default.
    Pass options.force_strategy=\"orchestrated\" only for explicit tests/overrides.
    """
    forced = str((options or {}).get("force_strategy") or "").strip().lower()
    if forced in {"fast", "tools", "orchestrated"}:
        return forced  # type: ignore[return-value]

    cfg = settings or get_settings()
    if cfg.enable_fast_chat and (is_trivial_chitchat(query) or is_simple_direct_chat(query)):
        return "fast"
    if cfg.enable_tool_agent and prefers_tool_agent_for_query(query):
        return "tools"
    if cfg.enable_tool_agent and should_route_chat_toward_tools(query):
        return "tools"

    fallback = str(cfg.chat_fallback_strategy or "fast").strip().lower()
    # Never auto-escalate Chat into multi-agent synthesizer stages.
    if fallback == "orchestrated":
        fallback = "fast"
    if fallback not in {"fast", "tools"}:
        fallback = "fast"
    if fallback == "tools" and not cfg.enable_tool_agent:
        fallback = "fast"
    if fallback == "fast" and not cfg.enable_fast_chat:
        # Fast disabled — tools if available, else explicit orchestrated only via force.
        return "tools" if cfg.enable_tool_agent else "orchestrated"
    return fallback  # type: ignore[return-value]


def _agent_metadata_from_context(options: ChatAgentOptions) -> dict:
    ctx = get_tool_execution_context()
    return {
        "planned_tools": list(ctx.planned) if ctx else [],
        "pending_tool_approvals": list(ctx.pending_approvals) if ctx else [],
        "tool_permission_mode": options.tool_permission_mode,
    }


@asynccontextmanager
async def agent_runtime_session(
    *,
    user_id: str,
    payload: ChatRequest,
    tool_registry: ToolRegistry,
    settings: Settings,
):
    """Load MCP tools + tool-permission context for one agent run."""
    options = ChatAgentOptions.from_request_options(payload.options)
    perm_token = activate_tool_execution_context(options, user_id=user_id)
    from app.core.deps import get_skill_catalog

    resolved = resolve_skill_for_request(
        get_skill_catalog(),
        user_id=user_id,
        payload=payload,
    )
    skill_token = activate_skill_context(
        allowed_tools=resolved.skill.allowed_tools if resolved else None,
        skill_name=resolved.skill.name if resolved else None,
    )
    mcp_token = tool_registry.activate_session_tools({})
    try:
        if settings.enable_runtime_mcp:
            from app.services.mcp_tools import discover_user_mcp_tools

            session_tools, _errors = await discover_user_mcp_tools(
                store=get_mcp_server_store(),
                user_id=user_id,
                settings=settings,
            )
            tool_registry.deactivate_session_tools(mcp_token)
            mcp_token = tool_registry.activate_session_tools(session_tools)
        yield options
    finally:
        tool_registry.deactivate_session_tools(mcp_token)
        deactivate_tool_execution_context(perm_token)
        deactivate_skill_context(skill_token)


def _build_augmented_prompt(
    *,
    payload: ChatRequest,
    user_id: str,
    settings: Settings,
    user_memory_store,
) -> str:
    from app.core.deps import get_skill_catalog

    skill_match = resolve_skill_for_request(
        get_skill_catalog(),
        user_id=user_id,
        payload=payload,
    )
    query = get_last_user_message(payload).content
    return augment_system_prompt(
        get_system_prompt(),
        user_query=query,
        user_id=user_id,
        settings=settings,
        user_memory_store=user_memory_store,
        skill_addendum=skill_match.skill.system_addendum if skill_match else None,
        skill_name=skill_match.skill.name if skill_match else None,
    )


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
    strategy = resolve_chat_execution_strategy(query, settings, payload.options)
    from app.core.deps import get_user_memory_store

    user_memory_store = get_user_memory_store()
    augmented_prompt = _build_augmented_prompt(
        payload=payload,
        user_id=user_id,
        settings=settings,
        user_memory_store=user_memory_store,
    )
    agent_options = ChatAgentOptions.from_request_options(payload.options)

    if strategy == "fast":
        response = await run_fast_chat(
            query=query,
            chat_history=history,
            llm_gateway=llm_gateway,
            settings=settings,
            system_prompt=augmented_prompt,
            user_id=user_id,
            user_memory_store=user_memory_store,
        )
        response.tool_permission_mode = agent_options.tool_permission_mode
        return response

    if strategy == "tools":
        block_token = reset_live_blocks()
        async with agent_runtime_session(
            user_id=user_id,
            payload=payload,
            tool_registry=tool_registry,
            settings=settings,
        ) as options:
            try:
                text = await run_tool_agent(
                    query=query,
                    system_prompt=augmented_prompt,
                    chat_history=history,
                    tool_registry=tool_registry,
                    settings=settings,
                    user_id=user_id,
                )
                blocks = get_live_blocks()
                meta = _agent_metadata_from_context(options)
                _persist_planned_tasks(
                    user_id=user_id,
                    conversation_id=payload.conversation_id,
                    planned_tools=[item.model_dump() for item in meta["planned_tools"]],
                )
                return ChatResponse(
                    message=text,
                    sources=[],
                    blocks=blocks,
                    sentiment=detect_sentiment(query) if settings.enable_sentiment_tone else None,
                    planned_tools=meta["planned_tools"],
                    pending_tool_approvals=meta["pending_tool_approvals"],
                    tool_permission_mode=meta["tool_permission_mode"],
                )
            except Exception:
                return await run_fast_chat(
                    query=query,
                    chat_history=history,
                    llm_gateway=llm_gateway,
                    settings=settings,
                    system_prompt=augmented_prompt,
                    user_id=user_id,
                    user_memory_store=user_memory_store,
                )
            finally:
                restore_live_blocks(block_token)

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
    response = await service.run_mode(
        mode="chat",
        query=query,
        system_prompt=augmented_prompt,
        chat_history=history,
        conversation_id=payload.conversation_id,
        user_id=user_id,
        top_k=payload.top_k or settings.default_top_k,
        score_threshold=payload.score_threshold,
        options=merge_workflow_options(payload),
        use_rag=workflow.use_rag if workflow else is_document_grounded_query(query),
        include_trace=workflow.include_trace if workflow else False,
        persist_memory=workflow.persist_memory if workflow else False,
        max_steps=workflow.max_steps if workflow else 6,
    )
    response.tool_permission_mode = agent_options.tool_permission_mode
    return response


def _persist_planned_tasks(
    *,
    user_id: str,
    conversation_id: Optional[str],
    planned_tools: list,
) -> None:
    if not planned_tools:
        return
    from app.core.deps import get_agent_task_store

    get_agent_task_store().record_planned_tools(
        user_id=user_id,
        conversation_id=conversation_id,
        planned_tools=planned_tools,
    )


async def execute_chat_mode_stream(
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
) -> AsyncIterator[dict]:
    """Stream chat execution events (`block`, `status`, `final`)."""
    settings = get_settings()
    query = get_last_user_message(payload).content
    strategy = resolve_chat_execution_strategy(query, settings, payload.options)

    if strategy != "tools":
        response = await execute_chat_mode(
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
        yield {"type": "final", "response": response.model_dump()}
        return

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def on_block(block) -> None:
        await queue.put({"type": "block", "block": block.model_dump()})

    block_cb_token = activate_block_event_callbacks([on_block])
    block_token = reset_live_blocks()

    async def run_agent() -> ChatResponse:
        async with agent_runtime_session(
            user_id=user_id,
            payload=payload,
            tool_registry=tool_registry,
            settings=settings,
        ) as options:
            from app.core.deps import get_user_memory_store

            user_memory_store = get_user_memory_store()
            history = [{"role": msg.role, "content": msg.content} for msg in payload.messages[:-1]]
            augmented_prompt = _build_augmented_prompt(
                payload=payload,
                user_id=user_id,
                settings=settings,
                user_memory_store=user_memory_store,
            )
            text = await run_tool_agent(
                query=query,
                system_prompt=augmented_prompt,
                chat_history=history,
                tool_registry=tool_registry,
                settings=settings,
                user_id=user_id,
            )
            blocks = get_live_blocks()
            meta = _agent_metadata_from_context(options)
            _persist_planned_tasks(
                user_id=user_id,
                conversation_id=payload.conversation_id,
                planned_tools=[item.model_dump() for item in meta["planned_tools"]],
            )
            return ChatResponse(
                message=text,
                sources=[],
                blocks=blocks,
                sentiment=detect_sentiment(query) if settings.enable_sentiment_tone else None,
                planned_tools=meta["planned_tools"],
                pending_tool_approvals=meta["pending_tool_approvals"],
                tool_permission_mode=meta["tool_permission_mode"],
            )

    yield {"type": "status", "message": "Running tools…"}
    task = asyncio.create_task(run_agent())
    try:
        while True:
            if task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.25)
                yield event
            except asyncio.TimeoutError:
                if task.done():
                    break
        response = await task
        yield {"type": "final", "response": response.model_dump()}
    except Exception as exc:
        if not task.done():
            task.cancel()
        yield {"type": "error", "message": str(exc)}
    finally:
        restore_live_blocks(block_token)
        deactivate_block_event_callbacks(block_cb_token)


def record_post_chat_memory(
    *,
    user_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    settings = get_settings()
    if not user_id:
        return
    if settings.enable_user_memory:
        from app.core.deps import get_user_memory_store

        store = get_user_memory_store()
        store.record_turn(user_id=user_id, user_message=user_message, assistant_message=assistant_message)
        for fact in extract_memory_facts_heuristic(user_message, assistant_message):
            store.record_fact(user_id=user_id, fact=fact)
    if settings.enable_memory_consolidation:
        from app.core.deps import get_memory_consolidation_service

        get_memory_consolidation_service().record_turn(
            user_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )


__all__ = [
    "ChatExecutionStrategy",
    "agent_runtime_session",
    "execute_chat_mode",
    "execute_chat_mode_stream",
    "record_post_chat_memory",
    "resolve_chat_execution_strategy",
]
