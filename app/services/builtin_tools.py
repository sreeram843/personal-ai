"""Built-in tools registered in ToolRegistry and exposed to the chat agent."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.schemas.chat import RetrievedChunk
from app.schemas.tool import ToolCapability, ToolRiskClass, ToolSpec
from app.services.context_compression import compress_context_block
from app.services.live_block_collector import append_live_block
from app.services.live_data_manager import LiveDataManager
from app.services.live_tool_hub import LiveToolHub
from app.services.self_rag import retrieve_user_documents_with_self_rag
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.ollama import OllamaClient
from app.services.tool_registry import ToolRegistry
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

CHAT_AGENT_ROLE = "chat_agent"
_LIVE_TOOL_SENTINEL = "get_game_score"


def _query_input(inputs: dict) -> str:
    return str(inputs.get("user_query") or inputs.get("query") or "").strip()


def _format_document_hits(
    chunks: List[RetrievedChunk],
    *,
    query: str = "",
    settings: Optional[Settings] = None,
) -> str:
    if not chunks:
        return "No matching internal documents were found."
    sections: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata or {}
        label = str(metadata.get("path") or metadata.get("name") or metadata.get("title") or chunk.id)
        body = chunk.text
        if settings is not None and query:
            body = compress_context_block(query, body, settings=settings)
        sections.append(f"[{index}] {label} (score={chunk.score:.2f})\n{body}")
    return "\n\n".join(sections)


def register_builtin_tools(
    registry: ToolRegistry,
    web_search: WebSearchService,
    *,
    live_data: Optional[LiveDataManager] = None,
    ollama: Optional[OllamaClient] = None,
    vector_store: Optional[VectorStore] = None,
    settings: Optional[Settings] = None,
    llm_gateway: Optional[LLMGateway] = None,
    model_profile: Optional[WorkflowModelProfile] = None,
) -> None:
    """Register read-only tools used by the chat agent."""
    if registry.get_tool(_LIVE_TOOL_SENTINEL):
        return

    if live_data is None:
        from app.core.config import get_settings
        from app.services.adapter_cache import build_adapter_cache

        cfg = settings or get_settings()
        live_data = LiveDataManager(
            web_search=web_search,
            cache=build_adapter_cache(cfg),
            settings=cfg,
        )

    hub = LiveToolHub(live_data=live_data, web_search=web_search, settings=settings or get_settings())

    def _live_executor(method: Callable[..., Awaitable[Any]]) -> Callable[[dict, float], Awaitable[str]]:
        async def executor(inputs: dict, timeout: float) -> str:
            kwargs = {k: v for k, v in inputs.items() if v not in (None, "")}
            result = await method(**kwargs)
            if result.block is not None:
                append_live_block(result.block)
            return result.summary

        return executor

    async def web_executor(inputs: dict, timeout: float) -> str:
        results = await web_search.search_with_page_excerpts(_query_input(inputs))
        return WebSearchService.format_results_for_context(results) or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def fetch_url_executor(inputs: dict, timeout: float) -> str:
        url = str(inputs.get("url") or inputs.get("href") or _query_input(inputs)).strip()
        return await web_search.scrape_url_content(url)

    async def web_research_executor(inputs: dict, timeout: float) -> str:
        if settings is None or not settings.perplexity_api_key:
            return "ERROR: Perplexity web research is not configured"
        from app.services.web_providers.perplexity import perplexity_search

        results = await perplexity_search(
            query=_query_input(inputs),
            api_key=settings.perplexity_api_key,
            timeout=float(timeout),
        )
        return WebSearchService.format_results_for_context(results) or "ERROR 404: LIVE DATA NOT VERIFIED"

    async def calendar_executor(inputs: dict, timeout: float) -> str:
        if settings is None or not settings.calendar_ics_url:
            return "ERROR: calendar ICS URL is not configured"
        from app.services.calendar_service import fetch_upcoming_events

        return await fetch_upcoming_events(settings.calendar_ics_url)

    async def document_search_executor(inputs: dict, timeout: float) -> str:
        if ollama is None or vector_store is None or settings is None:
            return "ERROR: document search is not configured"
        query = _query_input(inputs)
        user_id = str(inputs.get("user_id") or "").strip()
        if not query:
            return "ERROR: tool requires a non-empty query"
        if not user_id:
            return "ERROR: user scope missing for document search"

        retrieval = await retrieve_user_documents_with_self_rag(
            query=query,
            user_id=user_id,
            embed_client=ollama,
            vector_store=vector_store,
            settings=settings,
            pack_limit=settings.default_top_k,
            score_threshold=None,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
        )
        return _format_document_hits(retrieval.sources, query=query, settings=settings)

    specs: List[tuple[ToolSpec, Callable]] = [
        (
            ToolSpec(
                tool_id="fx_rate",
                name="FX Rate",
                description="Get a live FX exchange rate. Use for currency conversion questions (e.g. USD to INR).",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_fx_rate),
        ),
        (
            ToolSpec(
                tool_id="market_price",
                name="Market Price",
                description="Get live stock or commodity prices (not crypto — use get_crypto_price for BTC/ETH).",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_stock_price),
        ),
        (
            ToolSpec(
                tool_id="get_crypto_price",
                name="Crypto Price",
                description="Get live cryptocurrency prices (BTC, ETH, SOL, etc.) with 24h change.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_crypto_price),
        ),
        (
            ToolSpec(
                tool_id="weather",
                name="Weather",
                description="Get current weather conditions for a city or location.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_weather),
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
            _live_executor(hub.get_weather_forecast),
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
            _live_executor(hub.get_news),
        ),
        (
            ToolSpec(
                tool_id="find_nearby_places",
                name="Nearby Places",
                description=(
                    "Find restaurants, coffee shops, bars, hotels, or things to do near a city or neighborhood. "
                    "If the user says 'near me' without a location, ask which city or area to search."
                ),
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_nearby_places),
        ),
        (
            ToolSpec(
                tool_id="get_game_score",
                name="Game Score",
                description=(
                    "Get live or recent sports scores (NBA, NFL, MLB, NHL, etc.). "
                    "Pass team name and optional league."
                ),
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_game_score),
        ),
        (
            ToolSpec(
                tool_id="get_air_quality",
                name="Air Quality",
                description="Get current air quality (US AQI, PM2.5) for a city or location.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_air_quality),
        ),
        (
            ToolSpec(
                tool_id="get_sun_times",
                name="Sun Times",
                description="Get today's sunrise, sunset, and day length for a location.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_sun_times),
        ),
        (
            ToolSpec(
                tool_id="get_service_status",
                name="Service Status",
                description="Check outage/status for github, aws, cloudflare, openai, or slack.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_service_status),
        ),
        (
            ToolSpec(
                tool_id="get_flight_status",
                name="Flight Status",
                description="Look up in-flight status, gate, and delays for a flight number.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_flight_status),
        ),
        (
            ToolSpec(
                tool_id="get_package_tracking",
                name="Package Tracking",
                description="Track a package by tracking number across carriers.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_package_tracking),
        ),
        (
            ToolSpec(
                tool_id="get_transit_arrivals",
                name="Transit Arrivals",
                description="Get live transit arrival times for a stop or station.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_transit_arrivals),
        ),
        (
            ToolSpec(
                tool_id="get_traffic_eta",
                name="Traffic ETA",
                description="Get live drive time / traffic ETA between two places.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_traffic_eta),
        ),
        (
            ToolSpec(
                tool_id="get_gas_price",
                name="Gas Price",
                description="Get current gas/petrol prices near a location.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_gas_price),
        ),
        (
            ToolSpec(
                tool_id="get_betting_odds",
                name="Betting Odds",
                description="Get live betting odds or prediction-market prices for an event.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_betting_odds),
        ),
        (
            ToolSpec(
                tool_id="get_election_results",
                name="Election Results",
                description="Get live or recent election results for a race or region.",
                risk_class=ToolRiskClass.NETWORK,
                capabilities={ToolCapability.NETWORK_REQUEST},
                allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
            ),
            _live_executor(hub.get_election_results),
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

    if settings is not None and settings.firecrawl_api_key:
        specs.append(
            (
                ToolSpec(
                    tool_id="fetch_url",
                    name="Fetch URL",
                    description=(
                        "Scrape a specific web URL into clean Markdown for reading or citation. "
                        "Use when the user provides a link or you need full page content."
                    ),
                    risk_class=ToolRiskClass.NETWORK,
                    capabilities={ToolCapability.NETWORK_REQUEST},
                    allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
                ),
                fetch_url_executor,
            )
        )

    if settings is not None and settings.perplexity_api_key:
        specs.append(
            (
                ToolSpec(
                    tool_id="web_research",
                    name="Web Research",
                    description=(
                        "Extra web results via Perplexity Search API ($0.005/request). "
                        "Use when Tavily web_search results are thin or you want a second index."
                    ),
                    risk_class=ToolRiskClass.NETWORK,
                    capabilities={ToolCapability.NETWORK_REQUEST},
                    allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
                ),
                web_research_executor,
            )
        )

    if settings is not None and settings.calendar_ics_url:
        specs.append(
            (
                ToolSpec(
                    tool_id="calendar_events",
                    name="Calendar Events",
                    description=(
                        "List upcoming calendar events from the configured read-only ICS feed. "
                        "Use for schedule, meeting, or availability questions."
                    ),
                    risk_class=ToolRiskClass.NETWORK,
                    capabilities={ToolCapability.NETWORK_REQUEST},
                    allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
                ),
                calendar_executor,
            )
        )

    if ollama is not None and vector_store is not None and settings is not None:
        specs.append(
            (
                ToolSpec(
                    tool_id="search_documents",
                    name="Search Documents",
                    description=(
                        "Search the user's ingested documents and notes for relevant passages. "
                        "Use for questions about uploaded files, internal notes, or citations."
                    ),
                    risk_class=ToolRiskClass.SAFE,
                    capabilities={ToolCapability.DATABASE_QUERY},
                    allowed_roles={CHAT_AGENT_ROLE, "researcher", "coordinator"},
                ),
                document_search_executor,
            )
        )

    for spec, executor in specs:
        registry.register_tool(spec, executor)

    logger.info("Registered %s built-in tools", len(specs))


__all__ = [
    "CHAT_AGENT_ROLE",
    "register_builtin_tools",
]
