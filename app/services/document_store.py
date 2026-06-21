from __future__ import annotations

import uuid
from typing import List, Sequence

from sqlalchemy.orm import Session

from app.db.models import Document, User
from app.services.vector_store import StoredDocument


def record_ingested_documents(
    db: Session,
    user: User,
    documents: Sequence[StoredDocument],
    point_ids: Sequence[str],
) -> None:
    """Persist document metadata in Postgres linked to Qdrant point IDs."""
    for document, point_id in zip(documents, point_ids):
        metadata = dict(document.metadata)
        db.add(
            Document(
                user_id=user.id,
                qdrant_point_id=point_id,
                title=_document_title(metadata, document.text),
                source_path=metadata.get("path") if isinstance(metadata.get("path"), str) else None,
                metadata_json=metadata or None,
            )
        )
    db.commit()


def _document_title(metadata: dict, text: str) -> str:
    for key in ("title", "name", "path"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:512]
    return text.strip()[:80] or "Untitled document"
