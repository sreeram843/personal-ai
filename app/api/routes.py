from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.deps import get_ollama_client, get_vector_store
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage, RetrievedChunk
from app.schemas.documents import IngestRequest, IngestResponse
from app.schemas.persona import PersonaInfo, PersonaList, PersonaPreview, PersonaSwitchRequest
from app.services.ollama import OllamaClient
from app.services.vector_store import StoredDocument, VectorStore
from app.services.persona_manager import get_persona_manager
from api.persona_loader import PersonaDefinition, PersonaNotFoundError

router = APIRouter()

RAG_CITATION_RULE = "Use [path] or [title p.X]; if unsure, say 'I cannot verify this.'"


def _apply_persona(persona: PersonaDefinition, messages: List[dict[str, str]]) -> List[dict[str, str]]:
    augmented: List[dict[str, str]] = []
    augmented.append({"role": "system", "content": persona.system_prompt})
    augmented.extend({"role": shot["role"], "content": shot["content"]} for shot in persona.fewshots)
    augmented.extend(messages)
    return augmented


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    payload: IngestRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> IngestResponse:
    """Embed and store documents inside Qdrant."""

    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    texts = [doc.text for doc in payload.documents]
    embeddings = await ollama.embed(texts)
    stored_docs = [
        StoredDocument(text=doc.text, metadata=doc.metadata, id=doc.id)
        for doc in payload.documents
    ]
    await run_in_threadpool(vector_store.upsert, embeddings, stored_docs)
    return IngestResponse(count=len(stored_docs))


@router.post("/persona/switch", response_model=PersonaInfo)
async def switch_persona(payload: PersonaSwitchRequest) -> PersonaInfo:
    manager = get_persona_manager()
    try:
        persona = manager.switch(payload.name)
    except PersonaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PersonaInfo(persona=persona.name)


@router.get("/persona/active", response_model=PersonaInfo)
async def active_persona() -> PersonaInfo:
    manager = get_persona_manager()
    return PersonaInfo(persona=manager.current_name)


@router.post("/persona/reload", response_model=PersonaInfo)
async def reload_persona() -> PersonaInfo:
    manager = get_persona_manager()
    persona = manager.reload()
    return PersonaInfo(persona=persona.name)


@router.get("/persona/preview", response_model=PersonaPreview)
async def persona_preview() -> PersonaPreview:
    manager = get_persona_manager()
    preview = manager.persona_preview()
    return PersonaPreview(**preview)


@router.get("/persona/list", response_model=PersonaList)
async def persona_list() -> PersonaList:
    manager = get_persona_manager()
    return PersonaList(personas=manager.list_personas())


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
) -> ChatResponse:
    """Answer a chat request with the base model (no retrieval)."""

    if not payload.messages:
        raise HTTPException(status_code=400, detail="Missing chat messages")

    last_user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if last_user_message is None:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    manager = get_persona_manager()
    persona_definition, banned_patterns = manager.active_bundle()
    augmented_messages: List[dict[str, str]] = _apply_persona(
        persona_definition,
        [{"role": message.role, "content": message.content} for message in payload.messages],
    )

    response = await ollama.chat(augmented_messages, options=payload.options, stream=False)

    message = response.get("message", {}).get("content")
    if not message:
        raise HTTPException(status_code=500, detail="Unexpected response from Ollama")

    sanitized = manager.sanitize_response(message, patterns=banned_patterns)

    return ChatResponse(message=sanitized, sources=[])


@router.post("/rag_chat", response_model=ChatResponse)
async def rag_chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> ChatResponse:
    """Answer a chat request with context retrieved from Qdrant."""

    if not payload.messages:
        raise HTTPException(status_code=400, detail="Missing chat messages")

    last_user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if last_user_message is None:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    settings = get_settings()
    top_k = payload.top_k or settings.default_top_k

    query_embedding = await ollama.embed([last_user_message.content])
    results = await run_in_threadpool(
        vector_store.search,
        query_embedding[0],
        limit=top_k,
        score_threshold=payload.score_threshold,
    )

    sources: List[RetrievedChunk] = []
    context_sections: List[str] = []
    for idx, result in enumerate(results, start=1):
        payload_data = result.payload or {}
        text = payload_data.get("text", "")
        metadata = {k: v for k, v in payload_data.items() if k != "text"}
        sources.append(
            RetrievedChunk(
                id=str(result.id),
                score=float(result.score),
                text=text,
                metadata=metadata,
            )
        )
        if text:
            context_sections.append(f"[Source {idx}] {text}")

    context_block = "\n\n".join(context_sections)

    manager = get_persona_manager()
    persona_definition, banned_patterns = manager.active_bundle()
    base_messages = [{"role": message.role, "content": message.content} for message in payload.messages]
    augmented_messages: List[dict[str, str]] = _apply_persona(persona_definition, base_messages)

    if context_block:
        augmented_messages.insert(
            len(augmented_messages) - 1,
            {
                "role": "system",
                "content": (
                    f"Retrieved context follows. {RAG_CITATION_RULE}\n\n{context_block}"
                ),
            },
        )

    response = await ollama.chat(augmented_messages, options=payload.options, stream=False)

    message = response.get("message", {}).get("content")
    if not message:
        raise HTTPException(status_code=500, detail="Unexpected response from Ollama")

    sanitized = manager.sanitize_response(message, patterns=banned_patterns)

    return ChatResponse(message=sanitized, sources=sources)


__all__ = ["router"]
