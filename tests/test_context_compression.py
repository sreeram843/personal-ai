"""Tests for query-focused context compression."""

from __future__ import annotations

from app.core.config import Settings
from app.services.context_compression import (
    compress_context_block,
    compress_document_sections,
    compress_text_for_query,
)


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_compress_text_for_query_skips_short_text() -> None:
    text = "Short note."
    assert compress_text_for_query("budget forecast", text, min_chars_to_compress=400) == text


def test_compress_text_for_query_keeps_relevant_sentences() -> None:
    text = (
        "The office cafeteria serves pasta on Fridays. "
        "The Q3 budget forecast increased twelve percent year over year. "
        "Parking permits renew every January."
    )
    compressed = compress_text_for_query(
        "budget forecast Q3",
        text,
        target_ratio=0.5,
        min_chars_to_compress=80,
    )
    assert "budget forecast" in compressed.lower()
    assert "cafeteria" not in compressed.lower()
    assert len(compressed) < len(text)


def test_compress_document_sections_preserves_headers() -> None:
    text = (
        "[Document 1] report.md\n"
        "The office cafeteria serves pasta on Fridays. "
        "The Q3 budget forecast increased twelve percent year over year.\n\n"
        "[Document 2] notes.md\n"
        "Parking permits renew every January. Hiring roadmap spans two quarters."
    )
    compressed = compress_document_sections(
        "budget forecast Q3",
        text,
        settings=_settings(
            enable_context_compression=True,
            context_compression_min_chars=40,
            context_compression_block_max_chars=220,
        ),
    )
    assert compressed.startswith("[Document 1] report.md")
    assert "[Document 2] notes.md" in compressed
    assert "budget forecast" in compressed.lower()
    assert len(compressed) < len(text)


def test_compress_context_block_disabled_returns_original() -> None:
    text = "word " * 200
    result = compress_context_block(
        "budget forecast",
        text,
        settings=_settings(enable_context_compression=False),
    )
    assert result == text
