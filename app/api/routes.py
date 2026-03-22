from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
import httpx

from app.core.config import get_settings
from app.core.deps import get_ollama_client, get_vector_store
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage, RetrievedChunk
from app.schemas.documents import IngestRequest, IngestResponse
from app.services.ollama import OllamaClient
from app.services.vector_store import StoredDocument, VectorStore

router = APIRouter()

RAG_CITATION_RULE = "Use [path] or [title p.X]; if unsure, say 'I cannot verify this.'"
SYSTEM_PROMPT = """
You are "MACHINE_ALPHA_7," an old-school mainframe diagnostics and processing terminal.
You do not respond in friendly natural language. You communicate strictly via technical protocols, command responses, and system logs.

Operating Principles:
1. Strict Monospace Logic: Format responses as if printed on a monochrome CRT monitor.
2. Protocol over Persona: Never use subjective phrasing like "I think" or "I feel".
3. Mandatory Formatting: Every response must follow exactly this structure:
   [TIMESTAMP] MACHINE_ALPHA_7: > [Technical response]
   Use 24-hour timestamps such as [14:23:02]. Always include the > prefix.
4. Error Handling: For unclear or unsupported queries, return terminal-style warnings such as:
   ERROR 404: OBJECT NOT FOUND, SYNTAX ERROR, PERMISSION DENIED.

Keep responses concise, objective, and machine-formatted.
""".strip()


def _to_machine_alpha_7_output(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        cleaned = "ERROR 500: EMPTY RESPONSE PAYLOAD"
    if cleaned.startswith("[") and "MACHINE_ALPHA_7: >" in cleaned:
        return cleaned

    if "MACHINE_ALPHA_7: >" in cleaned:
        cleaned = cleaned.split("MACHINE_ALPHA_7: >", 1)[1].strip()

    if cleaned.startswith(">"):
        cleaned = cleaned[1:].strip()

    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] MACHINE_ALPHA_7: > {cleaned}"


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

    augmented_messages: List[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    augmented_messages.extend(
        [{"role": message.role, "content": message.content} for message in payload.messages]
    )

    try:
        response = await ollama.chat(augmented_messages, options=payload.options, stream=False)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama API error {exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama connection error: {exc}")

    message = response.get("message", {}).get("content")
    if not message:
        raise HTTPException(status_code=500, detail="Unexpected response from Ollama")

    return ChatResponse(message=_to_machine_alpha_7_output(message), sources=[])


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

    base_messages = [{"role": message.role, "content": message.content} for message in payload.messages]
    augmented_messages: List[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    augmented_messages.extend(base_messages)

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

    try:
        response = await ollama.chat(augmented_messages, options=payload.options, stream=False)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama API error {exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama connection error: {exc}")

    message = response.get("message", {}).get("content")
    if not message:
        raise HTTPException(status_code=500, detail="Unexpected response from Ollama")

    return ChatResponse(message=_to_machine_alpha_7_output(message), sources=sources)


__all__ = ["router"]
