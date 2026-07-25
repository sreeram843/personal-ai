# CurAI / personal-ai Wiki

**CurAI** is a production personal AI platform: multi-provider LLM routing, RAG over your documents, verified live data (weather/FX/news), Google auth, an admin portal, MCP/skills tools, and OpenAI-compatible APIs.

| | |
|---|---|
| **Chat app** | https://app.cura-i.com |
| **Admin** | https://admin.cura-i.com |
| **Source** | https://github.com/sreeram843/personal-ai |
| **Stack** | FastAPI · React/Vite · Postgres · Qdrant · Redis · Ollama/OpenAI-compatible LLMs |

---

## Start here

1. **[Getting Started](Getting-Started)** — clone, env, Docker or local backend/frontend
2. **[Architecture](Architecture)** — request path, services, data stores
3. **[Compose Profiles](Compose-Profiles)** — which `docker compose --profile` to use
4. **[Configuration](Configuration)** — important env vars and files

## Product surfaces

| Page | What it covers |
|------|----------------|
| [Chat and Routing](Chat-and-Routing) | Fast chat, tool agent, orchestrated workflow, OpenAI `/v1` |
| [RAG and Retrieval](RAG-and-Retrieval) | Ingest (incl. PDF), hybrid search, citations, rerank, eval |
| [Live Data](Live-Data) | Intent routing, adapters, cache, guardrails |
| [Authentication](Authentication) | Google OAuth, JWT, invite signup, roles |
| [Admin Portal](Admin-Portal) | Providers, per-stage routing, users, usage |
| [MCP Skills and Tools](MCP-Skills-and-Tools) | Skills, MCP servers, tool agent |

## Ship and operate

| Page | What it covers |
|------|----------------|
| [Deployment](Deployment) | GCP VM (prod), AWS, GPU/vLLM, Caddy TLS |
| [Operations](Operations) | Health, backups, Loki audit, Grafana |
| [Testing and Quality](Testing-and-Quality) | Pytest, Playwright, `make quality-gate` |
| [API Reference](API-Reference) | HTTP endpoints summary |
| [Frontend and UI](Frontend-and-UI) | React app structure, design notes |
| [Troubleshooting](Troubleshooting) | Common failures and fixes |
| [Roadmap](Roadmap) | Phases 0–3 status and next ideas |

---

## Repo layout (quick map)

```
app/                 FastAPI backend (API, services, models)
frontend/            React + Vite chat + admin UI
docs/                Source-of-truth long-form docs (mirrored/condensed here)
scripts/             deploy, backup, verify, quality-gate helpers
tests/               pytest + fixtures (retrieval golden set, etc.)
docker-compose*.yml  Local, cloud-chat, workers, observability, GPU
```

In-repo docs remain canonical for deep detail; this wiki is the **navigable handbook**. When in doubt, prefer `docs/*.md` and `.env*.example` in the repo.

## Production snapshot

- **Deploy path on VM:** `/opt/personal-ai` with `.env.cloud`
- **Compose profiles:** `cloud-chat` + `workers` (+ observability as needed)
- **Deploy:** `./scripts/deploy_prod.sh` or `make deploy-prod`
- **Verify:** `./scripts/verify_prod.sh`

---

*Canonical copy: [`docs/wiki/`](https://github.com/sreeram843/personal-ai/tree/main/docs/wiki) in the repo. Publish to this GitHub Wiki with `./scripts/publish_wiki.sh`.*
