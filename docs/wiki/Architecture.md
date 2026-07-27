# Architecture

CurAI is a **stateless FastAPI app** in front of Postgres (conversations, users, admin), Qdrant (embeddings), Redis (adapter cache / queues), and one or more LLM providers via an **LLM gateway**.

## High-level

```
Browser (React) ──JWT──► FastAPI
                           ├─ Auth / Admin / Conversations
                           ├─ Chat router (fast | tools | orchestrated)
                           ├─ RAG (embed → Qdrant → hybrid recall → rerank)
                           ├─ Live data adapters (FX, weather, news, …)
                           └─ OpenAI-compatible /v1 API
                ◄──────── Postgres · Qdrant · Redis · Ollama / cloud LLMs
```

## Chat execution strategies

Controlled by flags (`ENABLE_FAST_CHAT`, `ENABLE_TOOL_AGENT`) and model aliases on `/v1`:

| Path | When | Behavior |
|------|------|----------|
| **Fast chat** | Simple turns | Single-model reply; lower latency |
| **Tool agent** | Needs tools/MCP/skills | Agent loop with registered tools |
| **Orchestrated** | Complex / RAG-heavy | Planner → retrieve → synthesizer → reviewer → writer |

Per-stage provider/model selection comes from env **or** admin routing DB (production). See [Chat and Routing](Chat-and-Routing) and [Admin Portal](Admin-Portal).

## RAG path (summary)

1. **Ingest** — text / markdown / **PDF** (`POST /ingest`, `POST /ingest/files`)
2. **Chunk + embed** — Ollama `nomic-embed-text` (or configured embed)
3. **Store** — Qdrant collection, tenant-scoped
4. **Retrieve** — dense vectors + optional **hybrid** keyword (`MatchText`)
5. **Rerank** — score blend; optional **cross-encoder** (off by default)
6. **Cite** — writer preserves citation markers into the user-facing answer

Details: [RAG and Retrieval](RAG-and-Retrieval).

## Live data path (summary)

Live intents are classified, then resolvers run in order (FX → commodities → stocks → weather → news). Results are **verified** with timestamps or fail closed with `LIVE_DATA_NOT_VERIFIED`. Cached in Redis. Details: [Live Data](Live-Data).

## Multi-tenancy

- Users authenticated via Google (or disabled for local)
- Conversations and ingested docs scoped by user
- Roles: `user` | `support` | `admin`

## Observability

- `GET /health`, `GET /ready`, `GET /metrics`
- Optional Prometheus / Grafana / Loki compose profiles
- Audit logger `personal_ai.audit` for sensitive actions

## In-repo deep dives

- `docs/system-architecture.md`
- `docs/architecture-review.md`
- `docs/live-data-flow.md`
- `docs/ops-runbook.md`
