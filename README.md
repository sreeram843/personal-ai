# Personal AI

Monorepo for a local retrieval-augmented assistant. Backend is FastAPI + Qdrant + Ollama. Frontend is a Vite + React + Tailwind UI with two distinct visual modes.

## Stack Overview

- **Backend** (`app/`): FastAPI service with chat, RAG, smart routing, multi-agent workflows, persona management, and document ingestion.
- **Vector store**: Qdrant (local or remote) for document embeddings.
- **Model runtime**: Ollama serving chat + embedding models locally.
- **Frontend** (`frontend/`): React 19 + Vite 7 + Tailwind 3 with a CSS design token system, dual UI modes (Classic and Terminal), voice input, file uploads, and full chat history persistence.

## Prerequisites

- Python 3.9+ (3.11 recommended to avoid LibreSSL warnings on macOS)
- Node.js 18+
- [Ollama](https://ollama.com) running locally (`http://127.0.0.1:11434`)
  - Pull required models once: `ollama pull llama3:8b` and `ollama pull nomic-embed-text`
- Qdrant server (`http://127.0.0.1:6333` by default)
  - Docker example: `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant`

## Quick Start with Docker (Recommended)

Start all services with a single command:

```bash
# Copy environment variables
cp .env.example .env

# Start all services (app, ollama, qdrant)
docker compose up
```

Access the application:
- **App (Frontend + Backend API)**: http://localhost:8000
- **Ollama**: http://localhost:11434
- **Qdrant**: http://localhost:6333
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000

### Useful Docker Commands

```bash
# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f app
docker compose logs -f ollama

# Stop all services
docker compose down

# Restart all services
docker compose restart

# Pull Ollama models (run after services are up)
docker compose exec ollama ollama pull llama3:8b
docker compose exec ollama ollama pull nomic-embed-text

# Access backend shell
docker compose exec app /bin/bash
```

### Using Makefile (Optional Convenience)

```bash
make help          # Show all available commands
make build         # Build all images
make up            # Start all services
make down          # Stop all services
make logs          # View all logs
make pull-models   # Pull Ollama models
make clean         # Remove containers and volumes
make quality-gate  # Run the shared repo quality gate
```

### Runtime Modes (Local, Cloud, DMR)

This project supports three runtime modes using Docker Compose overlays.

1. **Local Ollama mode (default)**

```bash
make up
```

- Chat + embeddings run locally in the `ollama` container.
- Best for fully local/offline development.

2. **Cloud inference mode (OpenAI-compatible providers)**

```bash
cp .env.cloud.example .env.cloud
# Edit .env.cloud and enable exactly one provider block
make up-cloud
```

- Chat routes to your cloud provider (`LLM_DEFAULT_PROVIDER=openai`).
- Embeddings still run locally via Ollama (`nomic-embed-text`).
- Good balance for fast chat responses while keeping local RAG storage.

3. **Docker Model Runner mode (macOS only)**

```bash
make up-dmr
```

- Uses Docker Desktop Model Runner models via `docker-compose.dmr.yml`.
- The Ollama container is disabled in this mode.
- Recommended only when you specifically want DMR behavior on macOS.

### Cloud Provider Notes

- Providers are configured in `.env.cloud` (ignored by git) using the template in `.env.cloud.example`.
- Supported examples: GMI Cloud, Groq, Together AI, Fireworks AI.
- If one provider endpoint is unavailable, switch to another provider block in `.env.cloud`.

### Groq Cloud Flow (Tested)

Groq was validated end-to-end with this setup:

```bash
make up-cloud
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Reply in one sentence: what is 2+2?", "conversation_id": "test-groq-001"}' \
  | python3 -m json.tool
```

Expected behavior:
- API returns `200` with a chatbot message.
- Response is produced by the orchestration pipeline (planner/synthesizer/reviewer/writer).
- `sources` may include live web context when the workflow decides to fetch it.

### Verify Active Mode

Use this to confirm which backend provider is active inside the app container:

```bash
docker compose exec app env | grep -E "LLM_DEFAULT_PROVIDER|LLM_OPENAI_BASE_URL|OLLAMA_BASE_URL"
```

Interpretation:
- `LLM_DEFAULT_PROVIDER=openai` -> cloud chat mode.
- `LLM_DEFAULT_PROVIDER` unset (or `ollama`) -> local Ollama chat mode.
- `OLLAMA_BASE_URL=http://ollama:11434` should remain set for embeddings.

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

**Chat**

| Endpoint | Description | Response shape |
|----------|-------------|----------------|
| `POST /chat` | Standard chat via the orchestration engine | `{ "message": "..." }` |
| `POST /rag_chat` | Retrieval-grounded chat with source citations | `{ "message": "...", "sources": [...] }` |
| `POST /smart_chat` | Auto-routes between chat / RAG / workflow based on intent | `{ "message": "...", "sources": [...], "workflow": {...} }` |
| `POST /smart_chat/stream` | SSE stream of smart-routed progress events + final response | `text/event-stream` |
| `POST /workflow_chat` | Explicit multi-agent workflow with step trace | `{ "message": "...", "sources": [...], "workflow": { "steps": [...] } }` |
| `POST /workflow_chat/stream` | SSE stream of workflow progress events + final response | `text/event-stream` |
| `POST /ingest` | Upload documents for embedding and storage in Qdrant | `{ "count": <int> }` |

All chat endpoints accept `{ "messages": [...], "conversation_id": "..." }`. `/ingest` accepts `multipart/form-data` with a `files` field.

**Workflow runs (CRUD)**

| Endpoint | Description |
|----------|-------------|
| `POST /workflow_runs` | Create a workflow run record |
| `GET /workflow_runs` | List all workflow run records |
| `GET /workflow_runs/{run_id}` | Fetch a specific run |
| `POST /workflow_runs/{run_id}/pause` | Pause a run |
| `POST /workflow_runs/{run_id}/resume` | Resume a paused run |
| `POST /workflow_runs/{run_id}/cancel` | Cancel a run |

**Personas**

| Endpoint | Description |
|----------|-------------|
| `GET /personas` | List available personas |
| `POST /personas/switch` | Switch the active persona (`{ "name": "<persona>" }`) |
| `GET /personas/active` | Return the current active persona |
| `POST /personas/preview` | Return the merged system prompt for the active persona |

**Observability**

| Endpoint | Description |
|----------|-------------|
| `GET /metrics` | Prometheus metrics scrape endpoint |

### Typical Workflow

1. Start the backend (`uvicorn app.main:app --reload`).
2. Ingest documents via `/ingest` (Postman, curl, or the UI upload button). Friendly IDs such as `doc-1` are automatically normalized for Qdrant.
3. Call `/smart_chat` for intent-routed answers, `/rag_chat` for explicit retrieval with citations, or `/chat` for a direct baseline response.

## Frontend Setup

The frontend lives in `frontend/` and usually communicates with the FastAPI backend through `VITE_API_BASE_URL`.

Default local development settings are in `frontend/.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

For phone/LAN testing (Option A), set your machine IP:

```bash
VITE_API_BASE_URL=http://<your-mac-ip>:8000
```

Then run:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in a browser. Ensure the backend is running.

### Frontend Highlights

**Dual UI modes** (persisted in `localStorage`):
- **Classic mode** — Elevated-panel card layout with Space Grotesk typography, atmospheric ambient glow, and light/dark theme toggle.
- **Terminal mode** — Full-screen CRT aesthetic using the `MACHINE_ALPHA_7` persona, VT323 monospace font, phosphor color themes (green or amber), scanline overlay, and Web Audio print-tick feedback.

**Feature highlights:**
- Sidebar with conversation-mode toggle (Chat vs Smart), persona selector, new chat, and document upload.
- Chat bubbles with streaming text, per-message latency display, and RAG source cards.
- Smart mode (`/smart_chat`) auto-routes each message between direct chat, RAG, and multi-agent workflow.
- Workflow mode shows a live execution trace (planning → retrieval → synthesis → review → writing steps).
- Step memory events and per-step source citations displayed inline.
- Voice input toggle using the browser Web Speech API (Chrome recommended).
- File picker (accepts `.txt`, `.md`, `.pdf`) with per-file status updates and `aria-live` announcements.
- Full accessibility: skip link, `:focus-visible` outlines, ARIA labels and live regions, reduced-motion support.
- Dark/light theme, phosphor theme, chat history, conversation ID, and persona all persisted via `localStorage`.

**Font stack:**
- Classic mode: `Space Grotesk` (UI), `JetBrains Mono` (labels/meta)
- Terminal mode: `VT323`

**CSS architecture:**
- Design tokens via CSS custom properties (`--phosphor`, `--ui-bg`, `--ui-panel`, `--ui-border`, etc.) on `:root`.
- All component colours reference tokens — no hardcoded hex values in components.

To build for production:

```bash
npm run build
npm run preview
```

## Persona System

Three built-in personas live under `api/personas/`:

| Persona | Directory | Description |
|---------|-----------|-------------|
| `ideal_chatbot` | `api/personas/ideal_chatbot/` | Seven-trait governed assistant (default) |
| `therapist` | `api/personas/therapist/` | Empathetic listener with boundaries |
| `barney` | `api/personas/barney/` | Loyal, direct, high-confidence persona |

Each persona directory contains a standard set of files:
- `00_identity.md` — Mission and personality anchors
- `01_values.md` — How traits translate to behavior
- `02_decision_rules.md` — When to answer vs. ask
- `03_style.md` — Tone and vocabulary
- `04_emotion_rules.md` — Handling frustration and uncertainty
- `05_rubrics/` — Task-specific playbooks
- `06_negative_examples.md` — What NOT to do
- `07_glossary.md` — Preferred and banned terms
- `08_fewshots.jsonl` — Example interactions

**Runtime management:**
- `api/persona_loader.py` — disk hydration
- `app/services/persona_manager.py` — runtime switching and sanitisation

### Persona API Examples

```bash
# List personas
curl -s http://localhost:8000/personas | jq

# Switch to therapist
curl -s -X POST http://localhost:8000/personas/switch \\
  -H 'Content-Type: application/json' \\
  -d '{"name":"therapist"}'

# View active persona
curl -s http://localhost:8000/personas/active | jq

# Inspect merged system prompt
curl -s -X POST http://localhost:8000/personas/preview | jq '.persona, .fewshots'
```

## Trait System

This chatbot is governed by **seven core traits** that ensure consistent, principled behavior:

1. **Intuitive** — Clear vocabulary, uncluttered, happy to delegate.
2. **Coachable and Eager to Learn** — Accepts feedback, remembers context, adjusts.
3. **Contextually Smart** — Reads between lines, tracks constraints, infers intent.
4. **An Effective Communicator** — Right amount of detail, leads with answers.
5. **Reliable** — Honest about limitations, doesn't speculate on live data.
6. **Well-Connected** — Knows limits, suggests alternatives, respects boundaries.
7. **Secure** — Respects authorization, refuses unsafe requests.

**See [docs/traits.md](docs/traits.md)** for complete governance: operational definitions, decision rules, emotion handling, rubrics, negative examples, glossary, and validation tests.

## Testing

Run the full repo gate:

```bash
./scripts/quality_gate.sh
```

Run backend tests only:

```bash
./.venv/bin/python3 -m pytest
```

Run backend tests with coverage gate only:

```bash
./.venv/bin/python3 -m pytest --cov=app --cov=api --cov-fail-under=70
```

Run Playwright browser coverage only:

```bash
cd frontend
npm run test:e2e
npm run test:visual
```

Run lightweight docker compose smoke test only:

```bash
bash scripts/compose_smoke.sh
```

## Docs

- [docs/architecture.md](docs/architecture.md) — system structure and runtime responsibilities
- [docs/live-data-flow.md](docs/live-data-flow.md) — deterministic live-data path and guardrails
- [docs/ops-runbook.md](docs/ops-runbook.md) — startup, health checks, and troubleshooting
- [docs/deployment-checklist.md](docs/deployment-checklist.md) — pre-release readiness checklist
- [docs/traits.md](docs/traits.md) — trait governance, rubrics, and validation tests
- [docs/multi-trait-system.md](docs/multi-trait-system.md) — comprehensive multi-trait usage guide
- [docs/barney-persona.md](docs/barney-persona.md) — Barney persona design notes
- [docs/research-findings.md](docs/research-findings.md) — research and implementation findings
- [docs/multi-agent-improvement-roadmap.md](docs/multi-agent-improvement-roadmap.md) — multi-agent architecture roadmap
- [docker-setup.md](docker-setup.md) — detailed Docker + Compose setup guide

## Troubleshooting

- **Ollama 404 on `/api/embed`**: Ensure `nomic-embed-text` (or the configured embedding model) is pulled and the Ollama daemon is running.
- **Qdrant JSON ID errors**: The service now normalizes string IDs; check logs for warnings if a UUID is generated.
- **LibreSSL warnings on macOS system Python**: Switch to Python 3.11+ to use OpenSSL 3 and silence `urllib3` warnings.
- **Speech input unavailable**: Browsers without the Web Speech API fall back to text input; no additional configuration needed.

## Roadmap

- Backend conversation history persistence.
- Background ingestion workflows for large files.
- Deployment templates for Azure GPU VM with vLLM runtime.
- Mobile responsiveness pass and Playwright visual regression baseline.
- Additional persona types and runtime persona creation via API.
