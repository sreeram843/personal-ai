from __future__ import annotations

from typing import List, Sequence
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User
from app.schemas.documents import IngestDocument
from app.services.document_store import record_ingested_documents
from app.services.document_summary import build_document_summary_points
from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.services.object_storage import ObjectStorage
from app.services.ollama import OllamaClient
from app.services.sentence_window import stored_documents_from_sentence_chunks
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


async def _upsert_indexed_documents(
    *,
    db: Session,
    user: User,
    documents: Sequence[IngestDocument],
    settings: Settings,
    ollama: OllamaClient,
    vector_store: VectorStore,
    stored_docs: List[StoredDocument],
    llm_gateway: LLMGateway | None = None,
    model_profile: WorkflowModelProfile | None = None,
) -> int:
    summary_docs = await build_document_summary_points(
        documents,
        settings=settings,
        user_id=str(user.id),
        llm_gateway=llm_gateway,
        model_profile=model_profile,
    )
    indexed_docs = summary_docs + stored_docs
    if not indexed_docs:
        return 0

    embeddings = await ollama.embed([doc.text for doc in indexed_docs])
    point_ids = await run_in_threadpool(
        vector_store.upsert,
        embeddings,
        indexed_docs,
        user_id=str(user.id),
    )
    record_ingested_documents(db, user, indexed_docs, point_ids)
    return len(indexed_docs)


async def ingest_documents_for_user(
    *,
    db: Session,
    user: User,
    documents: Sequence[IngestDocument],
    settings: Settings,
    ollama: OllamaClient,
    vector_store: VectorStore,
    object_storage: ObjectStorage | None = None,
    llm_gateway: LLMGateway | None = None,
    model_profile: WorkflowModelProfile | None = None,
) -> int:
    if not documents:
        return 0

    if llm_gateway is None or model_profile is None:
        from app.core.deps import get_llm_gateway, get_workflow_model_profile

        llm_gateway = llm_gateway or get_llm_gateway()
        model_profile = model_profile or get_workflow_model_profile()

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
        stored_docs = stored_documents_from_sentence_chunks(
            documents,
            user_id=user_id,
            window_size=settings.llamaindex_sentence_window_size,
            prefer_llamaindex=True,
        )
        if not stored_docs:
            return 0
        return await _upsert_indexed_documents(
            db=db,
            user=user,
            documents=documents,
            settings=settings,
            ollama=ollama,
            vector_store=vector_store,
            stored_docs=stored_docs,
            llm_gateway=llm_gateway,
            model_profile=model_profile,
        )

    stored_docs = [
        StoredDocument(text=doc.text, metadata=doc.metadata, id=doc.id)
        for doc in documents
    ]
    return await _upsert_indexed_documents(
        db=db,
        user=user,
        documents=documents,
        settings=settings,
        ollama=ollama,
        vector_store=vector_store,
        stored_docs=stored_docs,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
    )


async def ingest_documents_for_user_id(
    *,
    db: Session,
    user_id: UUID,
    documents: Sequence[IngestDocument],
    settings: Settings,
    ollama: OllamaClient | None = None,
    vector_store: VectorStore | None = None,
    object_storage: ObjectStorage | None = None,
    llm_gateway: LLMGateway | None = None,
    model_profile: WorkflowModelProfile | None = None,
) -> int:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    if ollama is None or vector_store is None:
        from app.core.deps import (
            get_llm_gateway,
            get_object_storage,
            get_ollama_client,
            get_vector_store,
            get_workflow_model_profile,
        )

        ollama = ollama or get_ollama_client()
        vector_store = vector_store or get_vector_store()
        object_storage = object_storage or get_object_storage()
        llm_gateway = llm_gateway or get_llm_gateway()
        model_profile = model_profile or get_workflow_model_profile()
    return await ingest_documents_for_user(
        db=db,
        user=user,
        documents=documents,
        settings=settings,
        ollama=ollama,
        vector_store=vector_store,
        object_storage=object_storage,
        llm_gateway=llm_gateway,
        model_profile=model_profile,
    )
