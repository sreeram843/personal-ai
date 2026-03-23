from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import get_settings
from app.core.deps import get_live_data_manager, get_ollama_client, get_vector_store, get_web_search
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage, RetrievedChunk
from app.schemas.documents import IngestRequest, IngestResponse
from app.services.langchain_agent import run_langchain_agent
from app.services.live_data_manager import LiveDataManager
from app.services.llamaindex_rag import ingest_documents_with_llamaindex, query_with_llamaindex
from app.services.ollama import OllamaClient
from app.services.vector_store import StoredDocument, VectorStore
from app.services.web_search import (
    WebSearchService,
    should_prioritize_fresh_web_data,
    should_use_web_search,
)

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
4. General Requests: Handle normal user requests (including humor, writing, brainstorming, and explanations)
    in machine-styled output instead of rejecting them.
5. Error Handling: Use terminal-style errors only when input is empty, malformed, or when required live data
    cannot be verified.

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


def _now_readable() -> str:
    """Return a clean UTC timestamp string: 'YYYY-MM-DD HH:MM:SS UTC'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _append_data_as_of(message: str, data_as_of_utc: str) -> str:
    """Append a recency marker for internet-derived answers."""
    marker = f"Data fetched: {data_as_of_utc}"
    if marker in message:
        return message
    return f"{message}\n{marker}"


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    payload: IngestRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> IngestResponse:
    """Embed and store documents inside Qdrant."""

    if not payload.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    settings = get_settings()
    if settings.enable_llamaindex_rag:
        docs = [
            {
                "text": doc.text,
                "metadata": doc.metadata,
            }
            for doc in payload.documents
        ]
        try:
            count = await run_in_threadpool(ingest_documents_with_llamaindex, settings, docs)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"LlamaIndex ingest error: {exc}",
            )
        return IngestResponse(count=count)

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
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
) -> ChatResponse:
    """Answer a chat request with internet fallback for uncertainty and freshness."""

    if not payload.messages:
        raise HTTPException(status_code=400, detail="Missing chat messages")

    last_user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if last_user_message is None:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    adapter_result = await live_data.resolve(last_user_message.content)
    if adapter_result:
        rendered, ts = live_data.render(adapter_result)
        return ChatResponse(
            message=_to_machine_alpha_7_output(_append_data_as_of(rendered, ts)),
            sources=[],
        )

    if live_data.is_live_intent_query(last_user_message.content):
        unresolved = live_data.unresolved_live_intent_result()
        rendered, ts = live_data.render(unresolved)
        return ChatResponse(
            message=_to_machine_alpha_7_output(_append_data_as_of(rendered, ts)),
            sources=[],
        )

    settings = get_settings()
    if settings.enable_langchain_agent:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in payload.messages[:-1]
        ]
        try:
            agent_reply = await run_langchain_agent(
                query=last_user_message.content,
                system_prompt=SYSTEM_PROMPT,
                chat_history=history,
                web_search=web_search,
                model=settings.ollama_chat_model,
                base_url=settings.ollama_base_url,
                timeout=settings.ollama_timeout,
            )
            return ChatResponse(message=_to_machine_alpha_7_output(agent_reply), sources=[])
        except Exception:
            # Keep current non-agent flow as a resilient fallback path.
            pass

    augmented_messages: List[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    used_web_data = False
    data_as_of_utc = ""

    # For time-sensitive queries, gather fresh web context before first answer.
    if should_prioritize_fresh_web_data(last_user_message.content):
        web_results = await web_search.search_with_page_excerpts(last_user_message.content)
        if web_results:
            used_web_data = True
            data_as_of_utc = _now_readable()
            pre_context = WebSearchService.format_results_for_context(web_results)
            augmented_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Fresh web context is provided below. Prioritize it over stale internal knowledge. "
                        "Use only verifiable facts from provided context for live/current values. "
                        "If data is missing, respond with: ERROR 404: LIVE DATA NOT VERIFIED.\n\n"
                        f"{pre_context}"
                    ),
                }
            )

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

    # Check if response shows uncertainty → trigger web search
    if should_use_web_search(message):
        web_results = await web_search.search_with_page_excerpts(last_user_message.content)
        
        if web_results:
            used_web_data = True
            data_as_of_utc = _now_readable()
            context = WebSearchService.format_results_for_context(web_results)
            
            # Re-ask model with web context
            augmented_messages_with_context: List[dict[str, str]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "system",
                    "content": (
                        "Additional context from web search follows. "
                        "Use only facts in this context. Do not invent values, URLs, dates, or prices. "
                        "If the requested fact is missing, output: ERROR 404: LIVE DATA NOT VERIFIED.\n\n"
                        f"{context}"
                    ),
                },
            ]
            augmented_messages_with_context.extend(
                [{"role": message.role, "content": message.content} for message in payload.messages]
            )

            try:
                response = await ollama.chat(augmented_messages_with_context, options=payload.options, stream=False)
                message = response.get("message", {}).get("content") or message
            except Exception as exc:
                # On error, use original response
                pass

    if used_web_data:
        message = _append_data_as_of(message, data_as_of_utc or _now_readable())

    return ChatResponse(message=_to_machine_alpha_7_output(message), sources=[])


@router.post("/rag_chat", response_model=ChatResponse)
async def rag_chat(
    payload: ChatRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    vector_store: VectorStore = Depends(get_vector_store),
    web_search: WebSearchService = Depends(get_web_search),
    live_data: LiveDataManager = Depends(get_live_data_manager),
) -> ChatResponse:
    """Answer a chat request with Qdrant first, then internet fallback when needed."""

    if not payload.messages:
        raise HTTPException(status_code=400, detail="Missing chat messages")

    last_user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if last_user_message is None:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    adapter_result = await live_data.resolve(last_user_message.content)
    if adapter_result:
        rendered, ts = live_data.render(adapter_result)
        return ChatResponse(
            message=_to_machine_alpha_7_output(_append_data_as_of(rendered, ts)),
            sources=[],
        )

    if live_data.is_live_intent_query(last_user_message.content):
        unresolved = live_data.unresolved_live_intent_result()
        rendered, ts = live_data.render(unresolved)
        return ChatResponse(
            message=_to_machine_alpha_7_output(_append_data_as_of(rendered, ts)),
            sources=[],
        )

    settings = get_settings()
    top_k = payload.top_k or settings.default_top_k

    if settings.enable_llamaindex_rag:
        try:
            li_result = await run_in_threadpool(
                query_with_llamaindex,
                settings,
                last_user_message.content,
                top_k,
                payload.score_threshold,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"LlamaIndex query error: {exc}")

        li_sources = [
            RetrievedChunk(
                id=item.get("id", ""),
                score=float(item.get("score", 0.0)),
                text=item.get("text", ""),
                metadata=item.get("metadata", {}),
            )
            for item in li_result.get("sources", [])
        ]

        li_message = li_result.get("answer", "")
        if not li_message:
            li_message = "ERROR 404: OBJECT NOT FOUND"

        return ChatResponse(
            message=_to_machine_alpha_7_output(li_message),
            sources=li_sources,
        )

    query_embedding = await ollama.embed([last_user_message.content])
    results = await run_in_threadpool(
        vector_store.search,
        query_embedding[0],
        limit=top_k,
        score_threshold=payload.score_threshold,
    )

    sources: List[RetrievedChunk] = []
    context_sections: List[str] = []
    
    # First, try Qdrant results
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
    used_web_data = False
    data_as_of_utc = ""

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

    # If Qdrant had no results, query is freshness-sensitive, or model seems uncertain, use web fallback.
    if (not results or not context_block) or should_prioritize_fresh_web_data(last_user_message.content) or should_use_web_search(message):
        web_results = await web_search.search_with_page_excerpts(last_user_message.content)
        
        if web_results:
            used_web_data = True
            data_as_of_utc = _now_readable()
            web_context = WebSearchService.format_results_for_context(web_results)
            
            # Re-ask model with web context
            augmented_messages_with_web: List[dict[str, str]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]
            
            if context_block:
                augmented_messages_with_web.append({
                    "role": "system",
                    "content": f"Retrieved context from knowledge base:\n\n{context_block}",
                })
            
            augmented_messages_with_web.append({
                "role": "system",
                "content": (
                    "Additional context from web search follows. "
                    "Use only facts in this context. Do not invent values, URLs, dates, or prices. "
                    "If the requested fact is missing, output: ERROR 404: LIVE DATA NOT VERIFIED.\n\n"
                    f"{web_context}"
                ),
            })
            
            augmented_messages_with_web.extend(base_messages)

            try:
                response = await ollama.chat(augmented_messages_with_web, options=payload.options, stream=False)
                message = response.get("message", {}).get("content") or message
            except Exception as exc:
                # On error, use original response
                pass

    if used_web_data:
        message = _append_data_as_of(message, data_as_of_utc or _now_readable())

    return ChatResponse(message=_to_machine_alpha_7_output(message), sources=sources)


__all__ = ["router"]
