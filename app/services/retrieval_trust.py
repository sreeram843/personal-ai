"""Per-user retrieval trust weights stored as JSON.

Keyed by user_id then source identifier (metadata path, else chunk/evidence id).
Users are never mixed. Cold-start multiplier is 1.0.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from app.core.config import get_settings
from app.schemas.chat import RetrievedChunk

_REJECT_RE = re.compile(
    r"\b(unsupported|weak|unverified|cannot verify|can't verify)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])(?:\s+|\n+)+")

TrustStore = Dict[str, Dict[str, Dict[str, int]]]


def source_id_for_chunk(chunk: RetrievedChunk) -> str:
    """Prefer metadata path; fall back to the chunk/evidence id."""
    metadata = chunk.metadata or {}
    path = metadata.get("path")
    if isinstance(path, str) and path.strip():
        return path.strip()
    return str(chunk.id)


def source_ids_from_registry(
    evidence_ids: Sequence[str],
    registry: Dict[str, RetrievedChunk],
) -> List[str]:
    """Map evidence ids to stable source identifiers without mixing users."""
    source_ids: List[str] = []
    seen: set[str] = set()
    for evidence_id in evidence_ids:
        chunk = registry.get(evidence_id)
        source_id = source_id_for_chunk(chunk) if chunk is not None else str(evidence_id)
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
    return source_ids


def record_reviewer_verdict(user_id: str, source_ids: Sequence[str], review_text: str) -> None:
    """Update accept/reject counts from a reviewer note.

    Mentioned sources: reject when the mentioning sentence contains
    unsupported/weak/unverified/cannot verify; otherwise accept.
    Unmentioned sources: weak accept when the review is generally positive; else skip.
    """
    if not user_id or not source_ids:
        return
    unique_ids = _unique_source_ids(source_ids)
    if not unique_ids:
        return
    data = _load_store()
    bucket = data.setdefault(user_id, {})
    generally_negative = bool(_REJECT_RE.search(review_text or ""))
    for source_id in unique_ids:
        record = bucket.setdefault(source_id, {"accept": 0, "reject": 0})
        if _source_mentioned(review_text, source_id):
            if _source_has_reject_context(review_text, source_id):
                record["reject"] = int(record.get("reject") or 0) + 1
            else:
                record["accept"] = int(record.get("accept") or 0) + 1
        elif not generally_negative:
            record["accept"] = int(record.get("accept") or 0) + 1
    _save_store(data)


def trust_multiplier(user_id: str, source_id: str) -> float:
    """Return a score multiplier in (0.5, 1.15). Cold start is 1.0."""
    if not user_id or not source_id:
        return 1.0
    data = _load_store()
    record = (data.get(user_id) or {}).get(source_id) or {}
    accept = int(record.get("accept") or 0)
    reject = int(record.get("reject") or 0)
    if accept <= 0 and reject <= 0:
        return 1.0
    raw = (accept - reject) / (accept + reject + 1)
    if raw >= 0:
        return 1.0 + (0.15 * raw)
    return 1.0 + (0.5 * raw)


def _unique_source_ids(source_ids: Iterable[str]) -> List[str]:
    unique: List[str] = []
    seen: set[str] = set()
    for raw in source_ids:
        source_id = str(raw or "").strip()
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        unique.append(source_id)
    return unique


def _source_mentioned(text: str, source_id: str) -> bool:
    lowered = (text or "").lower()
    needle = source_id.lower().strip()
    if not needle:
        return False
    if needle in lowered:
        return True
    base = needle.rsplit("/", 1)[-1]
    return bool(base) and base != needle and base in lowered


def _source_has_reject_context(review_text: str, source_id: str) -> bool:
    sentences = _split_sentences(review_text) or [review_text]
    for sentence in sentences:
        if not _source_mentioned(sentence, source_id):
            continue
        if _REJECT_RE.search(sentence):
            return True
    return False


def _split_sentences(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]


def _store_path() -> Path:
    return Path(get_settings().retrieval_trust_path)


def _load_store() -> TrustStore:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _save_store(data: TrustStore) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


__all__ = [
    "record_reviewer_verdict",
    "source_id_for_chunk",
    "source_ids_from_registry",
    "trust_multiplier",
]
