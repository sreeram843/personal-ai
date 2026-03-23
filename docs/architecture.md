# Architecture

## System Overview

Personal AI is a single-repo local assistant with a FastAPI backend, a Vite/React frontend, deterministic live-data adapters, and an observability stack.

## Runtime Components

- `app/main.py`: creates the FastAPI app, applies CORS, and serves the built frontend from `/app/frontend_dist` in container mode.
- `app/api/routes.py`: owns `/chat`, `/rag_chat`, `/ingest`, and `/metrics`.
- `app/services/ollama.py`: wraps chat and embedding calls to Ollama.
- `app/services/vector_store.py`: stores and searches embedded chunks in Qdrant.
- `app/services/live_data_manager.py`: routes live-intent queries through deterministic providers before any generative fallback.
- `app/services/web_search.py`: provider integration layer for search, weather, FX, markets, and news.
- `app/services/adapter_cache.py`: Redis or in-memory cache for normalized adapter responses.
- `frontend/src/App.tsx`: top-level UI state, mode switching, uploads, and message history.
- `frontend/src/api.ts`: browser API client with localhost/remote fallback logic.

## Request Paths

### Standard Chat

1. The browser posts to `/chat`.
2. `LiveDataManager` checks whether the prompt is a live-intent query.
3. If a deterministic provider resolves the query, the backend returns a MACHINE_ALPHA_7 formatted response with provenance.
4. If the query is live-intent but cannot be verified, the backend returns a deterministic guardrail error.
5. Otherwise the request continues through Ollama, optionally enriched with fresh web context when the backend detects current-data intent.

### Retrieval-Augmented Chat

1. The browser posts to `/rag_chat`.
2. The same live-data guardrail runs first.
3. If the query is not a live-data case, the backend embeds the prompt with Ollama.
4. Qdrant returns the top matching chunks.
5. The backend builds the response prompt, runs Ollama, and returns answer plus sources.

### Document Ingestion

1. The UI uploads documents to `/ingest`.
2. The backend embeds document text with Ollama.
3. The resulting vectors and metadata are stored in Qdrant.
4. Future RAG queries can cite those chunks back to the user.

## Frontend State Model

- Conversation mode is stored in `localStorage` as `personal-ai-mode`.
- UI mode is stored in `localStorage` as `personal-ai-ui-mode`.
- Theme and phosphor state are stored in `localStorage` to persist across reloads.
- Chat history is kept in browser storage for local continuity.
- Upload status is ephemeral UI state and is reset by refresh.

## Data Stores

- Ollama: model execution and embedding generation.
- Qdrant: vector index for document retrieval.
- Redis: adapter response cache when enabled.
- Browser localStorage: UI state and chat history.
- Prometheus: time-series metrics storage.
- Grafana: dashboard and datasource state.

## Observability

- `/metrics` exposes Prometheus metrics.
- `live_adapter_requests_total` records adapter hits, status, source, and cache-hit state.
- `live_adapter_latency_seconds` records provider latency.
- Prometheus scrapes both itself and the app.
- Grafana is provisioned against the internal `http://prometheus:9090` compose address.

## Quality Gate

The repo-level gate is `scripts/quality_gate.sh`. It validates compose config, runs security checks, compiles Python, runs pytest, lints the frontend, builds the frontend, runs Playwright flow and visual tests, and builds the backend image.

## Key Constraints

- Live-intent queries should never fall through to unverifiable generation.
- The containerized app serves the frontend from the backend container, so UI changes require rebuilding the app image for compose-based verification.
- Local developer experience supports both direct backend/frontend development and full compose-based stack verification.