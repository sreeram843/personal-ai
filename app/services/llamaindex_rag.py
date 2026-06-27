from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.services.sentence_window import SentenceWindowChunk, WINDOW_METADATA_KEY


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


def parse_sentence_window_chunks_with_llamaindex(
    text: str,
    metadata: Dict[str, Any],
    *,
    window_size: int,
) -> List[SentenceWindowChunk]:
    """Parse sentence-window chunks using LlamaIndex's SentenceWindowNodeParser."""
    mods = _import_llamaindex()
    Document = mods["Document"]
    SentenceWindowNodeParser = mods["SentenceWindowNodeParser"]

    parser = SentenceWindowNodeParser.from_defaults(
        window_size=window_size,
        window_metadata_key=WINDOW_METADATA_KEY,
    )
    document = Document(text=text, metadata=dict(metadata))
    nodes = parser.get_nodes_from_documents([document])

    chunks: List[SentenceWindowChunk] = []
    for index, node in enumerate(nodes):
        sentence = str(getattr(node, "text", "") or "").strip()
        if not sentence:
            continue
        node_metadata = dict(getattr(node, "metadata", {}) or {})
        window = str(node_metadata.get(WINDOW_METADATA_KEY) or sentence).strip() or sentence
        node_metadata[WINDOW_METADATA_KEY] = window
        node_metadata.setdefault("sentence_index", index)
        node_metadata["chunking"] = "sentence_window_llamaindex"
        chunks.append(SentenceWindowChunk(sentence=sentence, window=window, metadata=node_metadata))
    return chunks


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
    user_id: str,
) -> int:
    """Backward-compatible helper returning chunk count for sentence-window ingest."""
    from app.services.sentence_window import stored_documents_from_sentence_chunks

    if not docs:
        return 0
    stored = stored_documents_from_sentence_chunks(
        docs,
        user_id=user_id,
        window_size=settings.llamaindex_sentence_window_size,
        prefer_llamaindex=True,
    )
    return len(stored)


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
        node_obj = getattr(node, "node", None)
        payload = dict(getattr(node_obj, "metadata", {}) or {})
        text = str(getattr(node_obj, "text", "") or "")
        source_items.append(
            {
                "id": str(getattr(node_obj, "node_id", f"li-{idx}")),
                "score": score,
                "text": text,
                "metadata": payload,
            }
        )

    return {
        "answer": str(response),
        "sources": source_items,
    }


__all__ = [
    "ingest_documents_with_llamaindex",
    "parse_sentence_window_chunks_with_llamaindex",
    "query_with_llamaindex",
]
