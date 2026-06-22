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
- Loki: `http://localhost:3100` (logs; query via Grafana Explore or **App Logs** dashboard)

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
curl -s http://localhost:3100/ready
```

## Production VM (cloud-chat)

Deploy path is usually `/opt/personal-ai` with `.env.cloud` on the server.

```bash
cd /opt/personal-ai
./scripts/deploy_prod.sh
# or: make deploy-prod
```

This runs `compose up --build`, pulls `nomic-embed-text` into Ollama, migrates the DB, and hits `/health` + `/ready`.

**Compose profiles:** `app` depends on `ollama`, which is only defined with `--profile cloud-chat`. Plain `docker compose logs app` fails with “undefined service ollama”. Use container names or the full compose invocation:

```bash
docker logs --tail=100 personal-ai-app
docker logs --tail=100 personal-ai-ollama

docker compose \
  --profile cloud-chat --profile workers \
  -f docker-compose.yml -f docker-compose.cloud.yml \
  --env-file .env.cloud \
  ps
```

### Smart chat 404 on `/api/embed`

- Cause: `nomic-embed-text` not pulled in the Ollama container.
- Fix: `make pull-models-cloud` or re-run `./scripts/deploy_prod.sh`.

### Smart chat Qdrant `personal_ai_documents doesn't exist`

- Cause: fresh Qdrant volume; collection is only created on first ingest unless initialized.
- Fix (immediate, no redeploy):

```bash
docker exec personal-ai-app python -c \
  "from app.core.deps import get_vector_store; get_vector_store().ensure_collection(); print('ok')"
```

- Fix (after code update): app startup and RAG search auto-create the collection; `./scripts/deploy_prod.sh` also runs ensure step.

### Google OAuth / login not working

Symptoms: no Google button, “not configured” banner, `origin_mismatch` in browser console, or sign-in returns 401/503.

1. **Check server config** (on the VM):

```bash
cd /opt/personal-ai
./scripts/verify_prod_auth.sh
```

2. **`.env.cloud` must include** (then `./scripts/deploy_prod.sh`):

```bash
AUTH_DISABLED=false
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
JWT_SECRET=<long-random-secret>
CORS_ORIGINS=http://YOUR_PUBLIC_HOST:8000
```

3. **Google Cloud Console** → OAuth client → **Authorized JavaScript origins** must list the exact URL users open (scheme + host + port), e.g. `http://35.x.x.x:8000`. A mismatch causes the button to fail silently or with `origin_mismatch`.

4. **`AUTH_DISABLED=true`** (default) bypasses login entirely — OAuth will appear “broken” if you expected a login screen.

5. After changing `.env.cloud`, rebuild the app container (`compose up -d --build`) so env vars reload.

### Logo animation looks static

- Electrons orbit whenever motion is allowed (`prefers-reduced-motion` off).
- OS “Reduce motion” disables SVG/CSS animation by design.
- Redeploy latest image if the sidebar still shows a flat PNG — older builds predate the animated `CuraiLogo` component.

## Logs (local)

```bash
docker compose logs -f app
docker compose logs -f ollama
docker compose logs -f qdrant
docker compose logs -f redis
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f loki
docker compose logs -f promtail
```

For searchable logs in Grafana (Loki), open **Explore** → datasource **loki**, or the **App Logs** dashboard. See `monitoring/loki-log-queries.md` for LogQL examples.

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
- Loki receives container logs via Promtail (`personal-ai-*` containers only); Grafana uses `http://loki:3100`.
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