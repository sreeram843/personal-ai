import asyncio

import httpx

from app.core.config import Settings
from app.services.web_providers.firecrawl import firecrawl_scrape
from app.services.web_providers.perplexity import perplexity_search
from app.services.web_providers.router import resolve_search_provider, web_search
from app.services.web_providers.tavily import tavily_search
from app.services.web_search import WebSearchService


def test_resolve_search_provider_auto_prefers_tavily():
    settings = Settings(tavily_api_key="tvly-test", perplexity_api_key="pplx-test")
    assert resolve_search_provider(settings) == "tavily"


def test_resolve_search_provider_auto_perplexity_when_no_tavily():
    settings = Settings(tavily_api_key="", perplexity_api_key="pplx-test")
    assert resolve_search_provider(settings) == "perplexity"


def test_tavily_search_parses_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.tavily.com"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Example",
                        "url": "https://example.com",
                        "content": "Example snippet",
                        "score": 0.9,
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = _Client
    try:
        results = asyncio.run(
            tavily_search(query="test query", api_key="tvly-test", max_results=3)
        )
    finally:
        httpx.AsyncClient = original

    assert len(results) == 1
    assert results[0]["href"] == "https://example.com"
    assert results[0]["provider"] == "tavily"


def test_perplexity_search_parses_search_api_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.perplexity.ai"
        assert request.url.path == "/search"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "AI News",
                        "url": "https://example.com/a",
                        "snippet": "Latest developments in AI.",
                        "date": "2025-01-23",
                    },
                    {
                        "title": "Second hit",
                        "url": "https://example.com/b",
                        "snippet": "More context.",
                    },
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = _Client
    try:
        results = asyncio.run(
            perplexity_search(query="latest ai news", api_key="pplx-test", max_results=2)
        )
    finally:
        httpx.AsyncClient = original

    assert results[0]["body"] == "Latest developments in AI."
    assert results[0]["provider"] == "perplexity"
    assert results[0]["href"] == "https://example.com/a"
    assert len(results) == 2


def test_firecrawl_scrape_returns_markdown():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.firecrawl.dev"
        return httpx.Response(
            200,
            json={"data": {"markdown": "# Hello\n\nWorld"}},
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = _Client
    try:
        text = asyncio.run(
            firecrawl_scrape(url="https://example.com", api_key="fc-test")
        )
    finally:
        httpx.AsyncClient = original

    assert "Hello" in text


def test_web_search_service_uses_tavily_when_configured():
    calls = {"tavily": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.tavily.com":
            calls["tavily"] += 1
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Hit",
                            "url": "https://example.com/hit",
                            "content": "Body",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = _Client
    settings = Settings(tavily_api_key="tvly-test")
    service = WebSearchService(settings=settings)
    try:
        results = asyncio.run(service.search("quantum computing"))
    finally:
        httpx.AsyncClient = original

    assert calls["tavily"] == 1
    assert results[0]["title"] == "Hit"


def test_web_search_router_falls_back_to_perplexity_when_tavily_empty():
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "api.tavily.com":
            return httpx.Response(200, json={"results": []})
        if request.url.host == "api.perplexity.ai":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Fallback",
                            "url": "https://example.com/fallback",
                            "snippet": "Fallback snippet",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = _Client
    settings = Settings(tavily_api_key="tvly-test", perplexity_api_key="pplx-test")
    try:
        results = asyncio.run(
            web_search(query="fallback test", settings=settings, max_results=3)
        )
    finally:
        httpx.AsyncClient = original

    assert "api.tavily.com" in hosts
    assert "api.perplexity.ai" in hosts
    assert results[0]["body"] == "Fallback snippet"
