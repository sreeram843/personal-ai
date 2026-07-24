"""Validate ingest payloads for size and allowed file extensions."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Sequence

from fastapi import HTTPException

from app.core.config import Settings
from app.schemas.documents import IngestDocument
from app.services.ingest_service import ingest_document_payload_size


def _allowed_extensions(settings: Settings) -> set[str]:
    raw = (settings.ingest_allowed_extensions or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() if part.strip().startswith(".") else f".{part.strip().lower()}" for part in raw.split(",") if part.strip()}


def validate_ingest_documents(settings: Settings, documents: Sequence[IngestDocument]) -> None:
    if not documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    allowed = _allowed_extensions(settings)
    total_bytes = ingest_document_payload_size(documents)
    if total_bytes > settings.ingest_max_batch_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Ingest batch is too large ({total_bytes} bytes). "
                f"Limit is {settings.ingest_max_batch_bytes} bytes."
            ),
        )

    for document in documents:
        size = len(document.text.encode("utf-8"))
        if size > settings.ingest_max_document_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Document exceeds max size ({size} > {settings.ingest_max_document_bytes} bytes)."
                ),
            )
        path = str((document.metadata or {}).get("path") or "").strip()
        if not path or not allowed:
            continue
        suffix = PurePosixPath(path).suffix.lower()
        if suffix and suffix not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{suffix}' is not allowed. Allowed: {', '.join(sorted(allowed))}",
            )
