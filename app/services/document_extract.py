"""Extract plain text from uploaded document bytes for ingest."""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath

from fastapi import HTTPException


def _decode_text_bytes(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _extract_pdf_text(payload: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise HTTPException(
            status_code=500,
            detail="PDF support requires the pypdf package.",
        ) from exc

    try:
        reader = PdfReader(BytesIO(payload))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {exc}") from exc

    text = "\n\n".join(pages).strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="No extractable text found in PDF (scanned images are not supported yet).",
        )
    return text


def extract_document_text(*, filename: str, payload: bytes, content_type: str | None = None) -> str:
    """Return plain text for ingest from raw upload bytes."""
    if not payload:
        raise HTTPException(status_code=400, detail=f"{filename or 'upload'} is empty")

    suffix = PurePosixPath(filename or "").suffix.lower()
    normalized_type = (content_type or "").split(";")[0].strip().lower()
    is_pdf = suffix == ".pdf" or normalized_type == "application/pdf"

    if is_pdf:
        return _extract_pdf_text(payload)

    if suffix in {".txt", ".md", ".markdown", ""} or normalized_type.startswith("text/"):
        text = _decode_text_bytes(payload).strip()
        if not text:
            raise HTTPException(status_code=400, detail=f"{filename or 'upload'} has no text content")
        return text

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type for '{filename}'. Use .txt, .md, or .pdf.",
    )


__all__ = ["extract_document_text"]
