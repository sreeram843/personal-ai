"""Allowlisted live-data teaser for the public portfolio demo (weather + FX only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Optional

from app.core.config import Settings
from app.schemas.content_block import ContentBlock
from app.schemas.live_intent import LiveDataProvenance
from app.services.live_data_manager import LiveDataManager
from app.services.live_tool_hub import LiveToolHub
from app.services.web_search import WebSearchService

DemoLiveIntent = Literal["weather", "fx"]

_WEATHER_RE = re.compile(
    r"\b(weather|forecast|temperature|humid|raining|rain|snow|windy|climate)\b",
    re.IGNORECASE,
)
_FX_RE = re.compile(
    r"\b(fx|forex|exchange\s*rate|currency|usd|inr|eur|gbp|jpy|cad|aud|"
    r"dollar|rupee|euro|yen|pound)\b",
    re.IGNORECASE,
)


@dataclass
class DemoLiveTeaserResult:
    intent: Optional[DemoLiveIntent] = None
    context: str = ""
    blocks: List[ContentBlock] = field(default_factory=list)
    live: Optional[LiveDataProvenance] = None
    status_message: str = ""


def detect_demo_live_intent(query: str) -> Optional[DemoLiveIntent]:
    text = (query or "").strip()
    if not text:
        return None
    # Prefer weather when both match (e.g. "weather and USD" is rare; chips are distinct).
    if _WEATHER_RE.search(text):
        return "weather"
    if _FX_RE.search(text):
        return "fx"
    return None


def _provenance_from_block(block: ContentBlock, intent: DemoLiveIntent) -> LiveDataProvenance:
    data = block.data or {}
    source = str(data.get("source") or data.get("provider") or "live")
    fetched = str(
        data.get("asOf")
        or data.get("fetched_at")
        or data.get("fetched_at_utc")
        or datetime.now(timezone.utc).isoformat()
    )
    domain = block.type if block.type else ("weather_current" if intent == "weather" else "fx")
    return LiveDataProvenance(
        domain=domain,
        source=source,
        fetched_at_utc=fetched,
        confidence=1.0,
        verified=True,
    )


def demo_suggested_prompts() -> List[str]:
    return [
        "What has Sriram worked on recently?",
        "Tell me about his academic background",
        "How does he play cricket?",
        "What's the weather in Austin right now?",
        "What's the USD to INR exchange rate?",
    ]


def default_demo_intro(max_questions: int) -> str:
    return (
        "Try CurAI — ask about Sriram's work, academics, or cricket. "
        "You can also try a live weather or FX question. "
        f"You have {max_questions} free questions in this demo."
    )


async def fetch_demo_live_teaser(
    *,
    query: str,
    live_data: LiveDataManager,
    web_search: WebSearchService,
    settings: Settings,
) -> DemoLiveTeaserResult:
    intent = detect_demo_live_intent(query)
    if intent is None:
        return DemoLiveTeaserResult()

    hub = LiveToolHub(live_data=live_data, web_search=web_search, settings=settings)
    status = "Fetching live weather…" if intent == "weather" else "Fetching live FX rate…"

    try:
        if intent == "weather":
            tool = await hub.get_weather(query=query)
        else:
            tool = await hub.get_fx_rate(query=query)
    except Exception:
        return DemoLiveTeaserResult(
            intent=intent,
            status_message=status,
            context="",
        )

    summary = (tool.summary or "").strip()
    if not summary or summary.startswith("ERROR:"):
        return DemoLiveTeaserResult(intent=intent, status_message=status)

    blocks: List[ContentBlock] = [tool.block] if tool.block else []
    live = _provenance_from_block(tool.block, intent) if tool.block else LiveDataProvenance(
        domain="weather_current" if intent == "weather" else "fx",
        source="live",
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        verified=True,
    )
    context = (
        "## Live context (verified for this turn)\n"
        f"{summary}\n\n"
        "Use this live context when answering. If it does not fully answer the question, "
        "say what is known from live data and what is not."
    )
    return DemoLiveTeaserResult(
        intent=intent,
        context=context,
        blocks=blocks,
        live=live,
        status_message=status,
    )


__all__ = [
    "DemoLiveTeaserResult",
    "default_demo_intro",
    "demo_suggested_prompts",
    "detect_demo_live_intent",
    "fetch_demo_live_teaser",
]
