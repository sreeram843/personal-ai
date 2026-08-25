"""Tests for document text extraction (PDF + plain text)."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException
from pypdf import PdfWriter

from app.services.document_extract import extract_document_text

# Minimal valid PDF with extractable Helvetica text ("CurieAI PDF ingest marker").
_MINIMAL_TEXT_PDF = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length 68 >>stream
BT /F1 12 Tf 50 100 Td (CurieAI PDF ingest marker) Tj ET
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000384 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
461
%%EOF
"""


def test_extract_plain_text_and_markdown() -> None:
    assert extract_document_text(filename="notes.txt", payload=b"hello notes") == "hello notes"
    assert extract_document_text(filename="readme.md", payload=b"# Title\n\nBody") == "# Title\n\nBody"


def test_extract_pdf_text() -> None:
    text = extract_document_text(
        filename="report.pdf",
        payload=_MINIMAL_TEXT_PDF,
        content_type="application/pdf",
    )
    assert "CurieAI PDF ingest marker" in text


def test_extract_rejects_empty_pdf() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(HTTPException) as exc:
        extract_document_text(filename="blank.pdf", payload=buffer.getvalue())
    assert exc.value.status_code == 400
    assert "No extractable text" in str(exc.value.detail)


def test_extract_rejects_unsupported_type() -> None:
    with pytest.raises(HTTPException) as exc:
        extract_document_text(filename="virus.exe", payload=b"MZ")
    assert exc.value.status_code == 400
