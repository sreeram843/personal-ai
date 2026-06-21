from __future__ import annotations

import importlib
from typing import Any, Dict, List

from app.core.config import Settings
from app.services.builtin_tools import CHAT_AGENT_ROLE, build_langchain_tools_from_registry
from app.services.llm_metrics import observe_llm_call
from app.services.tool_registry import ToolRegistry


def _import_langchain() -> Dict[str, Any]:
    """Lazy-import LangChain modules so base app works without optional deps."""
    lc_agents = importlib.import_module("langchain.agents")
    lc_prompts = importlib.import_module("langchain.prompts")
    lc_messages = importlib.import_module("langchain_core.messages")
    lc_ollama = importlib.import_module("langchain_ollama")

    mods: Dict[str, Any] = {
        "AgentExecutor": getattr(lc_agents, "AgentExecutor"),
        "create_tool_calling_agent": getattr(lc_agents, "create_tool_calling_agent"),
        "ChatPromptTemplate": getattr(lc_prompts, "ChatPromptTemplate"),
        "MessagesPlaceholder": getattr(lc_prompts, "MessagesPlaceholder"),
        "tool": importlib.import_module("langchain.tools").tool,
        "AIMessage": getattr(lc_messages, "AIMessage"),
        "HumanMessage": getattr(lc_messages, "HumanMessage"),
        "SystemMessage": getattr(lc_messages, "SystemMessage"),
        "ChatOllama": getattr(lc_ollama, "ChatOllama"),
    }
    return mods


def _openai_compatible_base_url(base_url: str) -> str:
    """Normalize base URL for LangChain OpenAI client (expects .../v1 suffix)."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def _build_chat_llm(settings: Settings, mods: Dict[str, Any]) -> Any:
    """Use OpenAI-compatible cloud LLM when configured, otherwise local Ollama."""
    if settings.llm_default_provider == "openai" and settings.llm_openai_base_url:
        lc_openai = importlib.import_module("langchain_openai")
        ChatOpenAI = getattr(lc_openai, "ChatOpenAI")
        return ChatOpenAI(
            model=settings.llm_default_model,
            base_url=_openai_compatible_base_url(settings.llm_openai_base_url),
            api_key=settings.llm_openai_api_key or "not-needed",
            temperature=0,
            timeout=settings.llm_openai_timeout,
        )

    ChatOllama = mods["ChatOllama"]
    return ChatOllama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url.rstrip("/"),
        temperature=0,
    )


async def run_langchain_agent(
    *,
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    tool_registry: ToolRegistry,
    settings: Settings,
) -> str:
    """Run a LangChain tool-calling agent backed by the centralized ToolRegistry."""
    mods = _import_langchain()
    AgentExecutor = mods["AgentExecutor"]
    create_tool_calling_agent = mods["create_tool_calling_agent"]
    ChatPromptTemplate = mods["ChatPromptTemplate"]
    MessagesPlaceholder = mods["MessagesPlaceholder"]
    tool = mods["tool"]
    AIMessage = mods["AIMessage"]
    HumanMessage = mods["HumanMessage"]
    SystemMessage = mods["SystemMessage"]

    llm = _build_chat_llm(settings, mods)
    provider = settings.llm_default_provider
    model = settings.llm_default_model if provider == "openai" else settings.ollama_chat_model
    tools = build_langchain_tools_from_registry(
        tool_registry,
        role=CHAT_AGENT_ROLE,
        tool_decorator=tool,
    )
    if not tools:
        raise RuntimeError("No tools registered for chat agent")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=4,
        handle_parsing_errors=True,
    )

    normalized_history = []
    for item in chat_history:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        role = (item.get("role") or "user").lower()
        if role == "assistant":
            normalized_history.append(AIMessage(content=content))
        elif role == "system":
            normalized_history.append(SystemMessage(content=content))
        else:
            normalized_history.append(HumanMessage(content=content))

    async with observe_llm_call(provider=provider, model=model):
        result = await executor.ainvoke({"input": query, "chat_history": normalized_history})
    return str(result.get("output", "ERROR 500: AGENT RETURNED NO OUTPUT"))


__all__ = ["run_langchain_agent"]
