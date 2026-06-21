from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User
from app.schemas.documents import IngestDocument
from app.services.document_store import record_ingested_documents
from app.services.llamaindex_rag import ingest_documents_with_llamaindex
from app.services.object_storage import ObjectStorage
from app.services.ollama import OllamaClient
from app.services.vector_store import StoredDocument, VectorStore


def ingest_document_payload_size(documents: Sequence[IngestDocument]) -> int:
    return sum(len(doc.text.encode("utf-8")) for doc in documents)


def should_enqueue_ingest(settings: Settings, documents: Sequence[IngestDocument]) -> bool:
    if not settings.enable_background_workers:
        return False
    if settings.worker_queue_backend == "arq" and not settings.redis_url:
        return False
    if len(documents) >= settings.ingest_async_min_documents:
        return True
    return ingest_document_payload_size(documents) >= settings.ingest_async_min_bytes


async def ingest_documents_for_user(
    *,
    db: Session,
    user: User,
    documents: Sequence[IngestDocument],
    settings: Settings,
    ollama: OllamaClient,
    vector_store: VectorStore,
    object_storage: ObjectStorage | None = None,
) -> int:
    if not documents:
        return 0

    user_id = str(user.id)
    if object_storage is not None:
        for document in documents:
            filename = str(document.metadata.get("path") or document.metadata.get("title") or "upload.txt")
            storage_key = object_storage.put_bytes(
                user_id=user_id,
                filename=filename,
                payload=document.text.encode("utf-8"),
                content_type="text/plain",
            )
            document.metadata["storage_key"] = storage_key
            document.metadata["storage_uri"] = object_storage.get_uri(storage_key)
    if settings.enable_llamaindex_rag:
        docs = [
            {
                "text": doc.text,
                "metadata": {**doc.metadata, "user_id": user_id},
            }
            for doc in documents
        ]
        return await run_in_threadpool(ingest_documents_with_llamaindex, settings, docs, user_id)

    texts = [doc.text for doc in documents]
    embeddings = await ollama.embed(texts)
    stored_docs = [
        StoredDocument(text=doc.text, metadata=doc.metadata, id=doc.id)
        for doc in documents
    ]
    point_ids = await run_in_threadpool(
        vector_store.upsert,
        embeddings,
        stored_docs,
        user_id=user_id,
    )
    record_ingested_documents(db, user, stored_docs, point_ids)
    return len(stored_docs)


async def ingest_documents_for_user_id(
    *,
    db: Session,
    user_id: UUID,
    documents: Sequence[IngestDocument],
    settings: Settings,
    ollama: OllamaClient | None = None,
    vector_store: VectorStore | None = None,
    object_storage: ObjectStorage | None = None,
) -> int:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    if ollama is None or vector_store is None:
        from app.core.deps import get_ollama_client, get_object_storage, get_vector_store

        ollama = ollama or get_ollama_client()
        vector_store = vector_store or get_vector_store()
        object_storage = object_storage or get_object_storage()
    return await ingest_documents_for_user(
        db=db,
        user=user,
        documents=documents,
        settings=settings,
        ollama=ollama,
        vector_store=vector_store,
        object_storage=object_storage,
    )
