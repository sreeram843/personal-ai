from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

from app.core.config import Settings


def _import_llamaindex() -> Dict[str, Any]:
    """Lazy-import LlamaIndex modules so base app works without optional deps."""
    core = importlib.import_module("llama_index.core")
    core_node_parser = importlib.import_module("llama_index.core.node_parser")
    core_schema = importlib.import_module("llama_index.core.schema")
    li_embed = importlib.import_module("llama_index.embeddings.ollama")
    li_llm = importlib.import_module("llama_index.llms.ollama")
    li_qdrant = importlib.import_module("llama_index.vector_stores.qdrant")
    qdrant_client_mod = importlib.import_module("qdrant_client")

    return {
        "LISettings": getattr(core, "Settings"),
        "StorageContext": getattr(core, "StorageContext"),
        "VectorStoreIndex": getattr(core, "VectorStoreIndex"),
        "SentenceWindowNodeParser": getattr(core_node_parser, "SentenceWindowNodeParser"),
        "Document": getattr(core_schema, "Document"),
        "OllamaEmbedding": getattr(li_embed, "OllamaEmbedding"),
        "Ollama": getattr(li_llm, "Ollama"),
        "QdrantVectorStore": getattr(li_qdrant, "QdrantVectorStore"),
        "QdrantClient": getattr(qdrant_client_mod, "QdrantClient"),
    }


def _build_index(settings: Settings) -> Any:
    mods = _import_llamaindex()

    LISettings = mods["LISettings"]
    StorageContext = mods["StorageContext"]
    VectorStoreIndex = mods["VectorStoreIndex"]
    OllamaEmbedding = mods["OllamaEmbedding"]
    Ollama = mods["Ollama"]
    QdrantVectorStore = mods["QdrantVectorStore"]
    QdrantClient = mods["QdrantClient"]

    LISettings.llm = Ollama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        request_timeout=settings.ollama_timeout,
    )
    LISettings.embed_model = OllamaEmbedding(
        model_name=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
    )

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)


def ingest_documents_with_llamaindex(
    settings: Settings,
    docs: List[Dict[str, Any]],
) -> int:
    """Ingest documents through LlamaIndex with sentence-window chunking."""
    if not docs:
        return 0

    mods = _import_llamaindex()
    Document = mods["Document"]
    SentenceWindowNodeParser = mods["SentenceWindowNodeParser"]

    index = _build_index(settings)
    parser = SentenceWindowNodeParser.from_defaults(window_size=3)

    nodes = []
    for item in docs:
        text = item.get("text", "")
        metadata = item.get("metadata") or {}
        doc = Document(text=text, metadata=metadata)
        nodes.extend(parser.get_nodes_from_documents([doc]))

    if nodes:
        index.insert_nodes(nodes)
    return len(nodes)


def query_with_llamaindex(
    settings: Settings,
    query: str,
    top_k: int,
    score_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Query Qdrant through LlamaIndex and return answer plus sources."""
    if not query.strip():
        return {"answer": "", "sources": []}

    index = _build_index(settings)
    engine = index.as_query_engine(
        similarity_top_k=top_k,
        response_mode="compact",
    )

    response = engine.query(query)

    source_items: List[Dict[str, Any]] = []
    for idx, node in enumerate(getattr(response, "source_nodes", []) or [], start=1):
        score = float(getattr(node, "score", 0.0) or 0.0)
        if score_threshold is not None and score < score_threshold:
            continue
        source_items.append(
            {
                "id": str(getattr(getattr(node, "node", None), "node_id", f"li-{idx}")),
                "score": score,
                "text": str(getattr(getattr(node, "node", None), "text", "") or ""),
                "metadata": dict(getattr(getattr(node, "node", None), "metadata", {}) or {}),
            }
        )

    return {
        "answer": str(response),
        "sources": source_items,
    }


__all__ = [
    "ingest_documents_with_llamaindex",
    "query_with_llamaindex",
]
