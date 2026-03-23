from __future__ import annotations

import importlib
from typing import Any, Dict, List

from app.services.web_search import WebSearchService


def _import_langchain() -> Dict[str, Any]:
    """Lazy-import LangChain modules so base app works without optional deps."""
    lc_agents = importlib.import_module("langchain.agents")
    lc_prompts = importlib.import_module("langchain.prompts")
    lc_tools = importlib.import_module("langchain.tools")
    lc_messages = importlib.import_module("langchain_core.messages")
    lc_ollama = importlib.import_module("langchain_ollama")

    return {
        "AgentExecutor": getattr(lc_agents, "AgentExecutor"),
        "create_tool_calling_agent": getattr(lc_agents, "create_tool_calling_agent"),
        "ChatPromptTemplate": getattr(lc_prompts, "ChatPromptTemplate"),
        "MessagesPlaceholder": getattr(lc_prompts, "MessagesPlaceholder"),
        "tool": getattr(lc_tools, "tool"),
        "AIMessage": getattr(lc_messages, "AIMessage"),
        "HumanMessage": getattr(lc_messages, "HumanMessage"),
        "SystemMessage": getattr(lc_messages, "SystemMessage"),
        "ChatOllama": getattr(lc_ollama, "ChatOllama"),
    }


async def run_langchain_agent(
    *,
    query: str,
    system_prompt: str,
    chat_history: List[Dict[str, str]],
    web_search: WebSearchService,
    model: str,
    base_url: str,
    timeout: float,
) -> str:
    """Run a LangChain tool-calling agent with project-specific data tools."""
    mods = _import_langchain()
    AgentExecutor = mods["AgentExecutor"]
    create_tool_calling_agent = mods["create_tool_calling_agent"]
    ChatPromptTemplate = mods["ChatPromptTemplate"]
    MessagesPlaceholder = mods["MessagesPlaceholder"]
    tool = mods["tool"]
    AIMessage = mods["AIMessage"]
    HumanMessage = mods["HumanMessage"]
    SystemMessage = mods["SystemMessage"]
    ChatOllama = mods["ChatOllama"]

    @tool
    async def fx_rate_tool(user_query: str) -> str:
        """Get a live FX rate for queries like 'usd to inr'."""
        context = await web_search.build_live_fx_context(user_query)
        return context or "ERROR 404: LIVE DATA NOT VERIFIED"

    @tool
    async def market_price_tool(user_query: str) -> str:
        """Get live stock/commodity/crypto market prices from Yahoo/market APIs."""
        stock_ctx = await web_search.build_live_stock_context(user_query)
        if stock_ctx:
            return stock_ctx
        commodity_ctx = await web_search.build_live_commodity_context(user_query)
        if commodity_ctx:
            return commodity_ctx
        return "ERROR 404: LIVE DATA NOT VERIFIED"

    @tool
    async def weather_tool(user_query: str) -> str:
        """Get live weather conditions for a city/location (temperature, humidity, wind, rain)."""
        weather_ctx = await web_search.build_live_weather_context(user_query)
        return weather_ctx or "ERROR 404: LIVE DATA NOT VERIFIED"

    @tool
    async def weather_forecast_tool(user_query: str) -> str:
        """Get live weather forecast (next days) for a city/location."""
        forecast_ctx = await web_search.build_weather_forecast_context(user_query)
        return forecast_ctx or "ERROR 404: LIVE DATA NOT VERIFIED"

    @tool
    async def news_tool(user_query: str) -> str:
        """Get latest verified news headlines for a topic."""
        news_ctx = await web_search.build_live_news_context(user_query)
        return news_ctx or "ERROR 404: LIVE DATA NOT VERIFIED"

    @tool
    async def web_context_tool(user_query: str) -> str:
        """Search the web for current events and fresh public information."""
        results = await web_search.search_with_page_excerpts(user_query)
        return WebSearchService.format_results_for_context(results) or "ERROR 404: LIVE DATA NOT VERIFIED"

    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    tools = [
        fx_rate_tool,
        market_price_tool,
        weather_tool,
        weather_forecast_tool,
        news_tool,
        web_context_tool,
    ]
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

    result = await executor.ainvoke({"input": query, "chat_history": normalized_history})
    return str(result.get("output", "ERROR 500: AGENT RETURNED NO OUTPUT"))


__all__ = ["run_langchain_agent"]
