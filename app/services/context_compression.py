"""Query-focused context compression before LLM stages (LLMLingua-style packing)."""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Sequence, Tuple

from app.core.config import Settings
from app.services.retrieval_rerank import lexical_overlap_score
from app.services.sentence_window import split_sentences

logger = logging.getLogger(__name__)

_DOCUMENT_BLOCK_RE = re.compile(r"^(\[(?:Document|Source) \d+\][^\n]*\n)(.*)$", re.DOTALL)


def compress_text_for_query(
    query: str,
    text: str,
    *,
    target_ratio: float = 0.5,
    max_chars: Optional[int] = None,
    min_chars_to_compress: int = 400,
) -> str:
    """Extractively compress text, keeping sentences most relevant to the query."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) < min_chars_to_compress:
        return cleaned

    target_len = max(80, int(len(cleaned) * max(0.1, min(target_ratio, 1.0))))
    if max_chars is not None:
        target_len = min(target_len, max_chars)
    if target_len >= len(cleaned):
        return cleaned

    sentences = split_sentences(cleaned)
    if not sentences:
        return cleaned[:target_len].rstrip() + "…"

    if len(sentences) == 1:
        if len(sentences[0]) <= target_len:
            return sentences[0]
        return sentences[0][: max(0, target_len - 1)].rstrip() + "…"

    scored: List[Tuple[int, float, str]] = [
        (index, lexical_overlap_score(query, sentence), sentence) for index, sentence in enumerate(sentences)
    ]
    selected_indices: set[int] = set()
    total_chars = 0

    for index, _score, sentence in sorted(scored, key=lambda item: item[1], reverse=True):
        if index in selected_indices:
            continue
        next_total = total_chars + len(sentence) + (1 if selected_indices else 0)
        if next_total > target_len and selected_indices:
            continue
        selected_indices.add(index)
        total_chars = next_total
        if total_chars >= target_len:
            break

    if not selected_indices:
        selected_indices.add(max(scored, key=lambda item: item[1])[0])

    compressed = " ".join(sentences[index] for index in sorted(selected_indices))
    if len(compressed) > target_len:
        compressed = compressed[: max(0, target_len - 1)].rstrip() + "…"
    return compressed


def _try_llmlingua_compress(query: str, text: str, *, target_ratio: float) -> Optional[str]:
    try:
        from llmlingua import PromptCompressor
    except ImportError:
        return None

    try:
        compressor = PromptCompressor()
        rate = max(0.1, min(0.9, 1.0 - target_ratio))
        result = compressor.compress_prompt(text, question=query, rate=rate)
        compressed = str(result.get("compressed_prompt") or result.get("compressed_prompt_list", "")).strip()
        if isinstance(result.get("compressed_prompt_list"), list):
            compressed = " ".join(str(item) for item in result["compressed_prompt_list"]).strip()
        return compressed or None
    except Exception:
        logger.info("LLMLingua compression failed; using extractive fallback", exc_info=True)
        return None


def compress_context_block(
    query: str,
    text: str,
    *,
    settings: Settings,
) -> str:
    """Compress one context block if compression is enabled."""
    if not settings.enable_context_compression:
        return text

    cleaned = (text or "").strip()
    if not cleaned:
        return text
    if len(cleaned) < settings.context_compression_min_chars:
        return cleaned

    if settings.context_compression_use_llmlingua:
        llm_compressed = _try_llmlingua_compress(
            query,
            cleaned,
            target_ratio=settings.context_compression_target_ratio,
        )
        if llm_compressed:
            if (
                settings.context_compression_block_max_chars > 0
                and len(llm_compressed) > settings.context_compression_block_max_chars
            ):
                return llm_compressed[: settings.context_compression_block_max_chars - 1].rstrip() + "…"
            return llm_compressed

    return compress_text_for_query(
        query,
        cleaned,
        target_ratio=settings.context_compression_target_ratio,
        max_chars=settings.context_compression_block_max_chars,
        min_chars_to_compress=settings.context_compression_min_chars,
    )


def compress_document_sections(query: str, text: str, *, settings: Settings) -> str:
    """Compress multi-document retrieval blocks while preserving section headers."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    parts = re.split(r"(?=\[(?:Document|Source) \d+\])", cleaned)
    blocks: List[str] = []
    for part in parts:
        section = part.strip()
        if not section:
            continue
        match = _DOCUMENT_BLOCK_RE.match(section)
        if not match:
            blocks.append(compress_context_block(query, section, settings=settings))
            continue
        header, body = match.groups()
        blocks.append(header + compress_context_block(query, body.strip(), settings=settings))
    return "\n\n".join(blocks)


def compress_context_sections(
    query: str,
    sections: Sequence[str],
    *,
    settings: Settings,
) -> str:
    """Join and compress labeled context sections."""
    joined = "\n\n".join(section.strip() for section in sections if section and section.strip())
    if "[Document " in joined or "[Source " in joined:
        return compress_document_sections(query, joined, settings=settings)
    return compress_context_block(query, joined, settings=settings)


__all__ = [
    "compress_context_block",
    "compress_context_sections",
    "compress_document_sections",
    "compress_text_for_query",
]
