"""Compact evidence cards for context-efficient writer-stage prompts."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

from app.schemas.chat import RetrievedChunk

EVIDENCE_MARKER_RE = re.compile(r"\[\[evidence:([^\]]+)\]\]")

DEFAULT_MAX_CARD_CHARS = 200


def extract_cited_evidence_ids(text: str) -> set[str]:
    """Return evidence IDs referenced via [[evidence:<id>]] markers in draft text."""
    return {match.strip() for match in EVIDENCE_MARKER_RE.findall(text or "") if match.strip()}


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    first_period = cleaned.find(". ")
    if first_period != -1 and first_period + 1 <= max_chars:
        return cleaned[: first_period + 1].strip()
    window = cleaned[:max_chars]
    last_period = window.rfind(". ")
    if last_period > max_chars // 2:
        return window[: last_period + 1].strip()
    return window.rstrip() + "…"


def build_evidence_card(source: RetrievedChunk, *, max_chars: int = DEFAULT_MAX_CARD_CHARS) -> str:
    """Build a single compact evidence card from a retrieved chunk."""
    metadata = source.metadata or {}
    label = str(metadata.get("path") or metadata.get("name") or metadata.get("title") or source.id)
    trust = str(metadata.get("trust_lane") or metadata.get("source") or "unknown")
    score_bit = f", score={source.score:.2f}" if source.score else ""
    summary = _truncate_at_sentence(source.text, max_chars)
    return f"[evidence:{source.id}] {label} ({trust}{score_bit})\n{summary}"


def format_writer_evidence_context(
    registry: Dict[str, RetrievedChunk],
    *,
    cited_ids: Optional[Iterable[str]] = None,
    max_chars_per_card: int = DEFAULT_MAX_CARD_CHARS,
) -> str:
    """Format cited (or all) evidence as compact cards for the writer stage."""
    if not registry:
        return "No evidence available."

    if cited_ids is not None:
        selected = [registry[eid] for eid in cited_ids if eid in registry]
        if not selected:
            selected = list(registry.values())
    else:
        selected = list(registry.values())

    cards = [build_evidence_card(source, max_chars=max_chars_per_card) for source in selected]
    return "\n\n".join(cards)


__all__ = [
    "DEFAULT_MAX_CARD_CHARS",
    "EVIDENCE_MARKER_RE",
    "build_evidence_card",
    "extract_cited_evidence_ids",
    "format_writer_evidence_context",
]
