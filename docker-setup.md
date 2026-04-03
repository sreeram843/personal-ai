# Docker Setup Guide

This file is now a quick pointer to the current container workflow. The detailed operational steps live in `docs/ops-runbook.md`, which tracks the actual stack in `docker-compose.yml`.

## Current Compose Topology

- `app`: FastAPI serving both the API and the built frontend on port `8000`
- `ollama`: local LLM runtime on port `11434`
- `qdrant`: vector store on ports `6333` and `6334`
- `redis`: adapter cache backend on port `6379`
- `prometheus`: metrics scraper on port `9090`
- `grafana`: dashboards on port `3000`

## Quick Start

```bash
cp .env.example .env
docker compose up --build
docker compose exec ollama ollama pull llama3:8b
docker compose exec ollama ollama pull nomic-embed-text
```

Open `http://localhost:8000` for the application.

## Common Commands

```bash
docker compose logs -f app
docker compose logs -f ollama
docker compose logs -f qdrant
docker compose logs -f prometheus
docker compose logs -f grafana

docker compose down
docker compose down -v
docker compose ps
```

## Preferred References

- Architecture: `docs/architecture.md`
- Live data path: `docs/live-data-flow.md`
- Operations and troubleshooting: `docs/ops-runbook.md`
- Release readiness: `docs/deployment-checklist.md`
