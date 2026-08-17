# CurAI (Personal AI)

A **multi-user**, retrieval-augmented assistant with live data, tool calling, and
optional multi-agent workflows. FastAPI + PostgreSQL + Qdrant + Redis backend;
React 19 + Vite 7 + Tailwind chat UI with **Chat** and **Smart** modes,
server-synced history, and light/dark themes.

## What it does

| Capability | Status |
|------------|--------|
| Multi-user auth + Postgres persistence | ✅ JWT / OIDC (`AUTH_DISABLED=true` for local dev) |
| Per-user RAG (Qdrant scoped by `user_id`) | ✅ |
| Live data (FX, stocks, weather, news) | ✅ Deterministic short-circuit before LLM |
| Tool-calling agent (web + live tools) | ✅ `ToolRegistry` (`ENABLE_TOOL_AGENT`) |
| Unified chat with auto-routing (`chat` / `rag` / `workflow`) | ✅ `POST /chat` |
| Multi-agent workflow + SSE trace | ✅ `/workflow_chat`, `/chat/stream` |
| Cloud LLMs (Groq, DeepSeek, Gemini, …) | ✅ `cloud-chat` Compose profile |

Phases 0–3 of the roadmap are complete. See [docs/roadmap.md](docs/roadmap.md).

## Quick start (Docker)

```bash
cp .env.example .env
make up          # profile: local (Ollama chat + embeddings)
make db-migrate  # create Postgres tables (first run)
make pull-models # optional, if models aren't yet in the Ollama container
```

Open <http://localhost:8000>.

| Service | URL |
|---------|-----|
| App (API + frontend) | http://localhost:8000 |
| Ollama | http://localhost:11434 |
| Qdrant | http://localhost:6333 |
| Prometheus / Grafana | http://localhost:9090 / http://localhost:3000 |

Frontend dev server (optional): `cd frontend && npm install && npm run dev` →
http://localhost:5173.

Other runtime modes (`cloud-chat`, `gpu-vllm`, `remote`, `workers`) are switched via
Compose profiles — see [docs/compose-profiles.md](docs/compose-profiles.md).

## Routing table

| Audience | Where to go |
|----------|-------------|
| **Users** (run it) | This README · [docs/compose-profiles.md](docs/compose-profiles.md) |
| **Contributors** (develop) | [CONTRIBUTING.md](CONTRIBUTING.md) · [AGENTS.md](AGENTS.md) |
| **Architecture** | [docs/architecture.md](docs/architecture.md) · [docs/adr/](docs/adr/) |
| **API reference** | [docs/api.md](docs/api.md) |
| **Operations / runbooks** | [docs/runbooks/](docs/runbooks/) |
| **Testing & benchmarks** | [docs/testing-accuracy.md](docs/testing-accuracy.md) · [docs/model-stress-testing.md](docs/model-stress-testing.md) |
| **Assistant behavior** | [docs/traits.md](docs/traits.md) |
| **Frontend** | [frontend/README.md](frontend/README.md) · [frontend/CAPACITOR.md](frontend/CAPACITOR.md) |

## Configuration

Copy `.env.example` → `.env`. Key flags:

```bash
ENABLE_FAST_CHAT=true    # fast single-call path for trivial prompts
ENABLE_TOOL_AGENT=true   # tool-calling agent (default strategy)
ENABLE_OPENAI_API=true   # OpenAI-compatible /v1 endpoint
AUTH_DISABLED=true       # local dev only (no token required)
```

Full variable list: `.env.example`, `.env.cloud.example`, `.env.remote.example`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, branch/PR conventions, and
review expectations. Agents should read [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE). See [CHANGELOG.md](CHANGELOG.md) for release notes.
