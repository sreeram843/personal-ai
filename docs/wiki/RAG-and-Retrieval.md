# RAG and Retrieval

Grounded answers over user-uploaded knowledge: ingest → embed → Qdrant → retrieve → (optional) rerank → cite.

## Ingest

| Path | Content |
|------|---------|
| `POST /ingest` | JSON documents (text) |
| `POST /ingest/files` | Multipart file upload |

**Allowed extensions** (default): `.txt`, `.md`, `.pdf`  
PDFs are extracted server-side with **pypdf** (`app/services/document_extract.py`).

Limits (env, see `.env.example`):

- `INGEST_MAX_DOCUMENT_BYTES` — extracted text size after parse  
- `INGEST_MAX_UPLOAD_BYTES` — raw upload ceiling (PDFs need headroom)  
- `INGEST_MAX_BATCH_BYTES`, async thresholds for worker queue  

Large batches can enqueue background jobs when workers are enabled.

## Embeddings and storage

- Embed model: typically Ollama `nomic-embed-text` (`OLLAMA_EMBED_MODEL`)
- Collection: `QDRANT_COLLECTION` (default `personal_ai_documents`)
- Distance: Cosine; dimension must match embed model (`EMBEDDING_DIMENSION=768` for nomic)

Documents are tenant-scoped to the authenticated user.

## Retrieval

1. **Dense** vector search (`DEFAULT_TOP_K`)
2. **Hybrid** (default on): dense + Qdrant `MatchText` keyword recall (`RETRIEVAL_HYBRID_ENABLED`)
3. Score blend / rerank in `retrieval_rerank.py`
4. Optional **cross-encoder** slot (`RETRIEVAL_CROSS_ENCODER_*`) — HTTP TEI or local; **off by default**

## Citations

- `RAG_CITATION_RULE` and `ensure_answer_preserves_citations` keep markers through the writer stage
- UI surfaces sources (Sources panel) for grounded turns

## Eval

- Golden set: `tests/fixtures/retrieval_golden.json`
- Metrics: recall@k, MRR (`retrieval_metrics.py`)
- Gate: `tests/test_eval_retrieval_accuracy.py`

## Ops tips

- After embed model change, **re-ingest** (dimension / vectors must match)
- Backup Qdrant volume with prod backups — see [Operations](Operations)
- Cross-encoder needs a reachable TEI/HTTP service or local model install

## Code map

| Area | Location |
|------|----------|
| Extract / PDF | `app/services/document_extract.py` |
| Vector store | `app/services/vector_store.py` |
| Hybrid / sparse | `app/services/sparse_retrieval.py` |
| Rerank | `app/services/retrieval_rerank.py` |
| Cross-encoder | `app/services/cross_encoder_rerank.py` |
| Citations | `app/services/citations.py` |
| Document retrieval | `app/services/document_retrieval.py` |

## Related

- [Live Data](Live-Data) — web evidence scoring for non-corpus facts  
- [Testing and Quality](Testing-and-Quality)
