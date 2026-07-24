"""Citation helpers for RAG/workflow answers."""

from __future__ import annotations

from typing import Dict, Match, Sequence
from urllib.parse import urlparse

from app.schemas.chat import RetrievedChunk
from app.services.evidence_cards import EVIDENCE_MARKER_RE, extract_cited_evidence_ids

RAG_CITATION_RULE = "Use [path] or [title p.X]; if unsure, say 'I cannot verify this.'"

_UNVERIFIED_FALLBACK = (
    "I cannot verify key claims from the available evidence. "
    "Please review the cited sources or broaden retrieval before finalizing."
)


def _bare_domain(url: str) -> str:
    """Return just the host for a URL, or the input unchanged if it doesn't parse."""
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return url
    return netloc or url


def evidence_label(source: RetrievedChunk) -> str:
    """Human-readable citation label for a retrieved chunk."""
    metadata = source.metadata or {}
    is_web = str(metadata.get("source") or "").strip().lower() == "web"
    # Web sources store the full URL in `path`. Prefer the human-readable title
    # so citations read as `[Article Title]` rather than a long inline URL; if
    # there's no title, fall back to the bare domain instead of the full URL.
    key_order = ("title", "name", "path", "filename") if is_web else ("path", "name", "title", "filename")
    for key in key_order:
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        label = value.strip()
        if is_web and key == "path" and label.lower().startswith(("http://", "https://")):
            return _bare_domain(label)
        return label
    return str(source.id or "source")


def answer_has_path_citations(
    text: str,
    *,
    registry: Dict[str, RetrievedChunk],
    evidence_ids: Sequence[str],
) -> bool:
    """True when the answer already contains at least one [path]-style citation."""
    if not text:
        return False
    for evidence_id in evidence_ids:
        source = registry.get(evidence_id)
        if source is None:
            continue
        label = evidence_label(source)
        if f"[{label}]" in text:
            return True
        base = label.rsplit("/", 1)[-1]
        if base and f"[{base}]" in text:
            return True
    return False


def replace_evidence_markers_with_path_citations(
    text: str,
    registry: Dict[str, RetrievedChunk],
) -> str:
    """Convert [[evidence:<id>]] markers into user-facing [path] citations."""

    def _replace(match: Match[str]) -> str:
        evidence_id = match.group(1).strip()
        source = registry.get(evidence_id)
        if source is None:
            return match.group(0)
        return f"[{evidence_label(source)}]"

    return EVIDENCE_MARKER_RE.sub(_replace, text or "")


def ensure_answer_preserves_citations(
    *,
    final_answer: str,
    draft: str,
    registry: Dict[str, RetrievedChunk],
    evidence_ids: Sequence[str],
    require_markers: bool = True,
) -> str:
    """
    Guarantee citations reach the user-facing answer.

    Prefer the writer's prose when it already cites evidence (markers or [path]).
    If the writer drops citations that the synthesizer draft had, append a Sources
    footnote (or fall back to the draft with path citations).
    """
    answer = (final_answer or "").strip()
    draft_text = draft or ""

    if not require_markers or not evidence_ids:
        converted = replace_evidence_markers_with_path_citations(answer or draft_text, registry).strip()
        return converted or answer

    final_ids = extract_cited_evidence_ids(answer)
    has_paths = answer_has_path_citations(answer, registry=registry, evidence_ids=evidence_ids)
    if final_ids or has_paths:
        return replace_evidence_markers_with_path_citations(answer, registry).strip()

    draft_ids = extract_cited_evidence_ids(draft_text)
    cited = [eid for eid in draft_ids if eid in registry] or [
        eid for eid in evidence_ids if eid in registry
    ]
    if not cited:
        return answer or _UNVERIFIED_FALLBACK

    labels: list[str] = []
    seen: set[str] = set()
    for evidence_id in cited:
        label = evidence_label(registry[evidence_id])
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)

    if answer and answer != _UNVERIFIED_FALLBACK:
        footnote = "Sources: " + ", ".join(f"[{label}]" for label in labels)
        if footnote.lower() in answer.lower():
            return answer
        return f"{answer}\n\n{footnote}"

    restored = replace_evidence_markers_with_path_citations(draft_text, registry).strip()
    return restored or _UNVERIFIED_FALLBACK


__all__ = [
    "RAG_CITATION_RULE",
    "answer_has_path_citations",
    "ensure_answer_preserves_citations",
    "evidence_label",
    "replace_evidence_markers_with_path_citations",
]
