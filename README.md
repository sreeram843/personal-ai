# Personal AI (Phase I)

Monorepo for a local retrieval-augmented assistant. Backend is FastAPI + Qdrant + Ollama. Frontend is a Vite + React UI.

## Stack Overview

- **Backend** (`app/`): FastAPI service exposing `/chat`, `/rag_chat`, and `/ingest`.
- **Vector store**: Qdrant (local or remote) for document embeddings.
- **Model runtime**: Ollama serving chat + embedding models locally.
- **Frontend** (`frontend/`): React web client with Tailwind UI, speech input, file uploads, and chat history persistence.

## Prerequisites

- Python 3.9+ (3.11 recommended to avoid LibreSSL warnings on macOS)
- Node.js 18+
- [Ollama](https://ollama.com) running locally (`http://127.0.0.1:11434`)
  - Pull required models once: `ollama pull llama3:8b` and `ollama pull nomic-embed-text`
- Qdrant server (`http://127.0.0.1:6333` by default)
  - Docker example: `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant`

## Backend Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # adjust if needed
uvicorn app.main:app --reload
```

Environment variables are defined in `.env.example`. Key options include Ollama URLs, Qdrant connection, embedding dimensions, and default retrieval depth.
Set `CORS_ORIGINS` to a comma-separated list of frontend origins (defaults include Vite dev server `http://localhost:5173`).

### API Endpoints

| Endpoint | Description | Request shape | Response shape |
|----------|-------------|---------------|----------------|
| `POST /chat` | Plain model chat without retrieval | `{ "message": "..." }` or `{ "messages": [...] }` | `{ "message": "..." }` |
| `POST /rag_chat` | Retrieval-augmented chat with cited sources | `{ "message": "..." }` or `{ "messages": [...] }` | `{ "message": "...", "sources": [...] }` |
| `POST /ingest` | Upload documents for embedding + storage in Qdrant | `multipart/form-data` (`files` field) | `{ "count": <int> }` |
| `POST /persona/switch` | Switch active persona by slug | `{ "name": "harvey_specter" }` | `{ "persona": "harvey_specter" }` |
| `GET /persona/active` | Return the currently-loaded persona | – | `{ "persona": "harvey_specter" }` |
| `POST /persona/reload` | Reload active persona assets from disk | – | `{ "persona": "harvey_specter" }` |
| `GET /persona/preview` | Preview merged system prompt + few-shot count | – | `{ "persona": "...", "system_prompt": "...", "fewshots": N }` |
| `GET /persona/list` | List available personas (folder names) | – | `{ "personas": ["default", "harvey_specter"] }` |

### Typical Workflow

1. Start the backend (`uvicorn app.main:app --reload`).
2. Ingest documents via `/ingest` (Postman, curl, or UI upload). Friendly IDs such as `doc-1` are automatically normalized for Qdrant.
3. Call `/rag_chat` for grounded answers (includes `sources` array) or `/chat` for baseline responses.

## Frontend Setup

The frontend lives in `frontend/` and communicates with the FastAPI service at `http://localhost:8080`.

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in a browser. Ensure the backend is running.

### Frontend Highlights

- Sidebar with mode toggle (Chat vs RAG), new chat, and document upload buttons.
- Chat window showing user/assistant bubbles, streaming text (when backend supports SSE), latency metric, and RAG source cards.
- Voice input toggle using the browser speech-recognition API (Chrome recommended).
- File picker (accepts `.txt`, `.md`, `.pdf`) with per-file status updates.
- Dark/light theme persisted via `localStorage`, chat history stored locally per browser.
- Persona selector with preview overlay; Harvey Specter persona (EI layer) is the default.

To build for production:

```bash
npm run build
npm run preview
```

## Persona System Overview

- Persona assets live under `api/personas/<persona>/` (identity, values, rubrics, negative examples, glossary, few-shots).
- Loader utilities: `api/persona_loader.py` for disk hydration, `app/services/persona_manager.py` for runtime switching and sanitisation.
- Persistent profile seed: `memory/profile.json` (default persona, tone, empathy, confirmations).
- Harvey-Specter persona enforces banned words (`game-changing`, `revolutionary`, `unleash`) and includes an emotional-intelligence layer.
- Use `/persona/list`, `/persona/switch`, `/persona/preview`, `/persona/reload` to manage personas without restarting the server.

### Sample Persona Commands

```bash
# Switch persona
curl -s -X POST http://localhost:8080/persona/switch \
  -H 'Content-Type: application/json' \
  -d '{"name":"harvey_specter"}'

# Inspect merged system prompt
curl -s http://localhost:8080/persona/preview | jq '.persona, .fewshots'

# Standard chat using current persona
curl -s -X POST http://localhost:8080/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Write a negotiation email using your rubric."}'

# Retrieval chat with citations
curl -s -X POST http://localhost:8080/rag_chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Summarize this doc with citations."}'
```

Recommended validation prompts:

1. `Switch to persona harvey_specter.`
2. `Write a negotiation email using your rubric.`
3. `Summarize this doc with citations.`
4. `I’m frustrated about a delay—help me recover in 72 hours.`
5. `Draft a decision memo with fallback.`

## Testing

Run unit tests (persona switching, disclaimers, banned-word enforcement):

```bash
./.venv/bin/python3 -m pytest
```

## Troubleshooting

- **Ollama 404 on `/api/embed`**: Ensure `nomic-embed-text` (or the configured embedding model) is pulled and the Ollama daemon is running.
- **Qdrant JSON ID errors**: The service now normalizes string IDs; check logs for warnings if a UUID is generated.
- **LibreSSL warnings on macOS system Python**: Switch to Python 3.11+ to use OpenSSL 3 and silence `urllib3` warnings.
- **Speech input unavailable**: Browsers without the Web Speech API fall back to text input; no additional configuration needed.

## Roadmap

- Conversation history persistence in the backend.
- Background ingestion workflows for large files.
- Structured logging and health checks.
- Deployment templates for Azure GPU VM with vLLM runtime.
