"""Deterministic grounding gate for writer-stage answers.

Checks that load-bearing claims carry a valid [[evidence:id]] marker or a
[path] citation that matches the evidence registry. No LLM involved.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence

from app.services.evidence_cards import EVIDENCE_MARKER_RE

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])(?:\s+|\n+)+")
_PATH_CITE_RE = re.compile(r"(?<!\[)\[([^\[\]]+)\](?!\])")
_NUMBER_RE = re.compile(r"\d")
_HEDGE_RE = re.compile(
    r"\b("
    r"i cannot verify|i can't verify|cannot verify|can't verify|"
    r"i cannot confirm|i can't confirm|cannot confirm|can't confirm|"
    r"unable to verify|unable to confirm"
    r")\b",
    re.IGNORECASE,
)
_FACTUAL_VERB_RE = re.compile(
    r"\b("
    r"is|are|was|were|been|"
    r"has|have|had|"
    r"reports?|reported|announces?|announced|"
    r"confirms?|confirmed|shows?|showed|shown|"
    r"finds?|found|measures?|measured|"
    r"increas(?:e|es|ed|ing)|decreas(?:e|es|ed|ing)|"
    r"grew|grown|fell|fallen|"
    r"occurred|happened|contains?|includes?|requires?|"
    r"stated|says|said|indicates?|listed|"
    r"takes?|took|according"
    r")\b",
    re.IGNORECASE,
)


def extract_evidence_markers(text: str) -> list[str]:
    """Return [[evidence:id]] ids in appearance order."""
    return [match.strip() for match in EVIDENCE_MARKER_RE.findall(text or "") if match.strip()]


def ungrounded_claim_spans(
    text: str,
    evidence_ids: Sequence[str],
    registry_paths: Optional[Sequence[str]] = None,
) -> list[str]:
    """Return load-bearing claim sentences that lack a valid citation."""
    allowed_ids = {str(item).strip() for item in evidence_ids if str(item).strip()}
    path_aliases = _path_alias_set(registry_paths or [])
    gaps: list[str] = []
    for sentence in _split_sentences(text):
        if not _is_load_bearing_claim(sentence):
            continue
        if _sentence_is_grounded(sentence, allowed_ids, path_aliases):
            continue
        gaps.append(sentence)
    return gaps


def enforce_grounding_gate(
    *,
    writer_text: str,
    evidence_ids: Sequence[str],
    registry_paths: Optional[Sequence[str]] = None,
) -> tuple[bool, str]:
    """Pass when every load-bearing claim is cited, or when there is no evidence.

    Returns (True, "") on success. On failure the reason lists ungrounded spans.
    """
    if not evidence_ids:
        return True, ""
    gaps = ungrounded_claim_spans(writer_text, evidence_ids, registry_paths=registry_paths)
    if not gaps:
        return True, ""
    listed = "\n".join(f"- {span}" for span in gaps)
    return False, f"Ungrounded claims without matching evidence:\n{listed}"


def _split_sentences(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]


def _is_load_bearing_claim(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return False
    if _HEDGE_RE.search(stripped):
        return False
    return _has_proper_noun(stripped) or bool(_NUMBER_RE.search(stripped)) or bool(_FACTUAL_VERB_RE.search(stripped))


def _has_proper_noun(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z]+", sentence)
    for index, word in enumerate(words):
        if index == 0:
            continue
        if word[0].isupper() and len(word) >= 2:
            return True
    return False


def _sentence_is_grounded(sentence: str, allowed_ids: set[str], path_aliases: set[str]) -> bool:
    for marker in extract_evidence_markers(sentence):
        if marker in allowed_ids:
            return True
    if not path_aliases:
        return False
    for label in _PATH_CITE_RE.findall(sentence):
        if _citation_matches(label, path_aliases):
            return True
    return False


def _path_alias_set(registry_paths: Sequence[str]) -> set[str]:
    aliases: set[str] = set()
    for raw in registry_paths:
        value = str(raw or "").strip()
        if not value:
            continue
        lowered = value.lower()
        aliases.add(lowered)
        aliases.add(value.rsplit("/", 1)[-1].lower())
    return {item for item in aliases if item}


def _citation_matches(label: str, path_aliases: set[str]) -> bool:
    candidate = (label or "").strip().lower()
    if not candidate or candidate.startswith("evidence:"):
        return False
    if candidate in path_aliases:
        return True
    base = candidate.rsplit("/", 1)[-1]
    return bool(base) and base in path_aliases


__all__ = [
    "enforce_grounding_gate",
    "extract_evidence_markers",
    "ungrounded_claim_spans",
]
