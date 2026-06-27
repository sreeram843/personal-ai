"""Lightweight sentiment hints for dynamic tone (no model fine-tuning)."""

from __future__ import annotations

import re
from typing import Literal

SentimentLabel = Literal["neutral", "frustrated", "pleased", "urgent"]

_FRUSTRATED_MARKERS = (
    "not working",
    "doesn't work",
    "doesnt work",
    "broken",
    "useless",
    "wrong",
    "incorrect",
    "frustrated",
    "annoyed",
    "terrible",
    "awful",
    "still waiting",
    "again?",
    "why won't",
    "why wont",
)

_PLEASED_MARKERS = (
    "thank you",
    "thanks",
    "great job",
    "perfect",
    "awesome",
    "helpful",
    "appreciate",
    "well done",
    "love this",
)

_URGENT_MARKERS = (
    "asap",
    "urgent",
    "immediately",
    "right now",
    "deadline",
    "production down",
    "outage",
    "critical",
)


def detect_sentiment(text: str) -> SentimentLabel:
    lowered = (text or "").lower().strip()
    if not lowered:
        return "neutral"
    if any(marker in lowered for marker in _URGENT_MARKERS):
        return "urgent"
    if any(marker in lowered for marker in _FRUSTRATED_MARKERS) or re.search(r"!{2,}", lowered):
        return "frustrated"
    if any(marker in lowered for marker in _PLEASED_MARKERS):
        return "pleased"
    return "neutral"


def tone_instruction_for_sentiment(label: SentimentLabel) -> str:
    mapping = {
        "frustrated": (
            "## Tone guidance\n"
            "The user may be frustrated. Acknowledge the issue briefly, stay calm, "
            "give a direct fix or next step, and avoid unnecessary jargon."
        ),
        "pleased": (
            "## Tone guidance\n"
            "The user seems satisfied. Stay warm and concise; build on what worked."
        ),
        "urgent": (
            "## Tone guidance\n"
            "The user needs a fast answer. Lead with the conclusion, then minimal supporting detail."
        ),
        "neutral": "",
    }
    return mapping.get(label, "")


__all__ = ["SentimentLabel", "detect_sentiment", "tone_instruction_for_sentiment"]
