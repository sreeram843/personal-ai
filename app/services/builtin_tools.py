"""Built-in tools registered in ToolRegistry and exposed to the LangChain agent."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from app.schemas.tool import ToolCapability, ToolInvocationRequest, ToolRiskClass, ToolSpec
from app.services.tool_registry import ToolRegistry
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

CHAT_AGENT_ROLE = "chat_agent"


def _query_input(inputs: dict) -> str:
    return str(inputs.get("user_query") or inputs.get("query") or "").strip()


def _resolved_tool_query(*, query: str = "", user_query: str = "") -> str:
    return (query or user_query).strip()


def register_builtin_tools(registry: ToolRegistry, web_search: WebSearchService) -> None:
    """Register read-only network tools used by the chat agent."""
    if registry.get_tool("fx_rate"):
        return

    async def fx_executor(inputs: dict, timeout: float) -> str:
        context = await web_search.build_live_fx_context(_query_input(inputs))
        return context or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def market_executor(inputs: dict, timeout: float) -> str:
        query = _query_input(inputs)
        stock_ctx = await web_search.build_live_stock_context(query)
        if stock_ctx:
            return stock_ctx
        commodity_ctx = await web_search.build_live_commodity_context(query)
        return commodity_ctx or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def weather_executor(inputs: dict, timeout: float) -> str:
        context = await web_search.build_live_weather_context(_query_input(inputs))
        return context or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def forecast_executor(inputs: dict, timeout: float) -> str:
        context = await web_search.build_weather_forecast_context(_query_input(inputs))
        return context or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def news_executor(inputs: dict, timeout: float) -> str:
        context = await web_search.build_live_news_context(_query_input(inputs))
        return context or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def web_executor(inputs: dict, timeout: float) -> str:
        results = await web_search.search_with_page_excerpts(_query_input(inputs))
        return WebSearchService.format_results_for_context(results) or "ERROR 404: LIVE DATA NOT VERIFIED"

    specs: List[tuple[ToolSpec, Callable]] = [
        (
            ToolSpec(
                tool_id="fx_rate",
                name="FX Rate",
                description="Get a live FX rate for queries like 'usd to inr'.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            fx_executor,
        ),
        (
            ToolSpec(
                tool_id="market_price",
                name="Market Price",
                description="Get live stock, commodity, or crypto prices from market APIs.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            market_executor,
        ),
        (
            ToolSpec(
                tool_id="weather",
                name="Weather",
                description="Get live weather conditions for a city or location.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            weather_executor,
        ),
        (
            ToolSpec(
                tool_id="weather_forecast",
                name="Weather Forecast",
                description="Get a multi-day weather forecast for a city or location.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            forecast_executor,
        ),
        (
            ToolSpec(
                tool_id="news",
                name="News",
                description="Get latest verified news headlines for a topic.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            news_executor,
        ),
        (
            ToolSpec(
                tool_id="web_search",
                name="Web Search",
                description=(
                    "Search the web for current events, sports, product info, and any fresh public facts "
                    "not covered by the other tools."
                ),
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            web_executor,
        ),
    ]

    for spec, executor in specs:
        registry.register_tool(spec, executor)

    logger.info("Registered %s built-in tools", len(specs))


def build_langchain_tools_from_registry(
    registry: ToolRegistry,
    *,
    role: str,
    tool_decorator: Callable[..., Any],
) -> list[Any]:
    """Wrap ToolRegistry entries as LangChain tools for the tool-calling agent."""
    lc_tools: list[Any] = []

    for tool_id, spec in registry.list_tools_for_role(role).items():

        def _make_tool(bound_id: str, bound_spec: ToolSpec) -> Any:
            description = bound_spec.description

            async def impl(query: str = "", user_query: str = "") -> str:
                text = _resolved_tool_query(query=query, user_query=user_query)
                if not text:
                    return "ERROR: tool requires a non-empty query or user_query argument"
                result = await registry.invoke_tool(
                    ToolInvocationRequest(
                        tool_id=bound_id,
                        role=role,
                        inputs={"user_query": text, "query": text},
                    )
                )
                if result.success:
                    return result.output
                return result.error or "Tool invocation failed"

            impl.__name__ = bound_id
            impl.__doc__ = (
                f"{description}\n\n"
                "Args:\n"
                "    query: User question or search terms (preferred).\n"
                "    user_query: Alias for query."
            )
            return tool_decorator(impl)

        lc_tools.append(_make_tool(tool_id, spec))

    return lc_tools


__all__ = [
    "CHAT_AGENT_ROLE",
    "build_langchain_tools_from_registry",
    "register_builtin_tools",
]
