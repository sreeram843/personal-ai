# Ops Runbook

## Purpose

This runbook covers the local stack, observability endpoints, common verification commands, and first-pass troubleshooting.

## Services

- App: `http://localhost:8000`
- Ollama: `http://localhost:11434`
- Qdrant: `http://localhost:6333`
- Redis: `redis://localhost:6379/0`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Start and Stop

```bash
cp .env.example .env
docker compose up --build
docker compose down
docker compose down -v
```

## Health Checks

```bash
docker compose ps
curl -I http://localhost:8000/metrics
curl -I http://localhost:6333/collections
curl -s http://localhost:11434/api/tags
curl -s http://localhost:9090/-/healthy
curl -s http://localhost:3000/api/health
```

## Logs

```bash
docker compose logs -f app
docker compose logs -f ollama
docker compose logs -f qdrant
docker compose logs -f redis
docker compose logs -f prometheus
docker compose logs -f grafana
```

## Models

```bash
docker compose exec ollama ollama pull llama3:8b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama list
```

## Application Validation

```bash
python -m pytest
python scripts/security_checks.py
./scripts/quality_gate.sh

cd frontend && npm run test:e2e
cd frontend && npm run test:visual
```

## Metrics and Dashboards

- Prometheus should scrape `app:8000/metrics` from inside compose.
- Grafana should use `http://prometheus:9090` as its datasource URL.
- The default admin user is `admin`; override the password with `GRAFANA_ADMIN_PASSWORD`.

## Troubleshooting

### App is up but UI looks stale

- Cause: compose serves the built frontend from the backend image.
- Fix: rebuild the app image with `docker compose up --build`.

### Grafana cannot reach Prometheus

- Cause: using `localhost:9090` from inside the Grafana container.
- Fix: provision or configure the datasource to `http://prometheus:9090`.

### Live queries return deterministic errors

- Cause: provider failure or unsupported live-intent prompt.
- Fix: inspect `app` logs and Prometheus adapter metrics, then verify the external provider manually.

### RAG answers return no useful sources

- Cause: ingestion missing or retrieval threshold too strict.
- Fix: re-ingest documents, inspect Qdrant, and retest `/rag_chat`.

### Compose fails during startup

- Cause: stale containers, port conflicts, or image drift.
- Fix:

```bash
docker compose down
docker compose up --build
docker compose ps
```

## Escalation Path

1. Check container health and logs.
2. Check `/metrics` and Grafana datasource health.
3. Run `./scripts/quality_gate.sh` to detect regressions outside the current symptom.
4. Rebuild the stack if the app bundle may be stale.