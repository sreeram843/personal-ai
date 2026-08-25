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

Public URL: **https://app.cura-i.com**

**Full setup guide:** [prod-gcp-vm.md](./prod-gcp-vm.md) (DNS, firewall, OAuth Console, Caddy, verify).

Grafana (HTTPS subdomain): **https://grafana.app.cura-i.com** — see [monitoring-subdomain.md](./monitoring-subdomain.md).

Deploy path is usually `/opt/personal-ai` with `.env.cloud` on the server.

```bash
cd /opt/personal-ai
./scripts/setup_caddy.sh   # validates CADDY_* env + prints compose command
./scripts/deploy_prod.sh
# or: make deploy-prod
```

This runs `compose up --build`, pulls `nomic-embed-text` into Ollama, migrates the DB, then `./scripts/verify_prod.sh` (`/health`, `/ready`, HTTPS, auth config).

### Backup and restore (Postgres + Qdrant)

VM disk loss wipes conversations and embeddings. Take periodic backups:

```bash
cd /opt/personal-ai
./scripts/backup_prod.sh
# optional: BACKUP_DIR=/var/backups/personal-ai BACKUP_RETENTION_DAYS=14 ./scripts/backup_prod.sh
# or: make backup-prod
```

Each run writes `backups/<UTC-stamp>/`:

- `postgres.sql.gz` — `pg_dump` of the app database
- `qdrant_storage.tar.gz` — Qdrant named volume (when present)
- `qdrant-snapshot.json` — collection snapshot metadata (best-effort)

**Retention:** directories older than `BACKUP_RETENTION_DAYS` (default 14) under the backup root are deleted. Prefer copying backups off-VM (GCS/S3) and encrypt at rest with your storage provider’s CMEK/SSE.

**Restore on a fresh VM** (after `deploy_prod.sh` has created empty volumes):

```bash
cd /opt/personal-ai
./scripts/restore_prod.sh backups/<stamp>
# or: BACKUP_DIR=/var/backups/personal-ai ./scripts/restore_prod.sh <stamp>
# or: make restore-prod BACKUP_PATH=backups/<stamp>
# skip the Type RESTORE prompt (automation):
# RESTORE_CONFIRM=1 ./scripts/restore_prod.sh backups/<stamp>
./scripts/verify_prod.sh
```

The restore script overwrites live Postgres (and Qdrant when `qdrant_storage.tar.gz` is present). Interactive runs ask you to type `RESTORE`; set `RESTORE_CONFIRM=1` to skip the prompt.

**Manual fallback** (if the restore script is unavailable):

```bash
# 1) Postgres
gunzip -c backups/<stamp>/postgres.sql.gz | \
  docker compose --profile cloud-chat --profile workers \
    -f docker-compose.yml -f docker-compose.cloud.yml --env-file .env.cloud \
    exec -T postgres psql -U postgres -d personal_ai

# 2) Qdrant (stop qdrant, replace volume data, start)
docker stop personal-ai-qdrant
docker run --rm \
  -v personal-ai_qdrant_storage:/data \
  -v "$PWD/backups/<stamp>":/backup \
  alpine:3.20 \
  sh -c 'rm -rf /data/* && tar -C /data -xzf /backup/qdrant_storage.tar.gz'
docker start personal-ai-qdrant
```

Volume name may be `<compose-project>_qdrant_storage` — confirm with `docker volume ls | grep qdrant`. The restore script detects `${COMPOSE_PROJECT_NAME:-$(basename $PWD)}_qdrant_storage` the same way backup does.

### Audit events (Loki)

Sensitive actions emit JSON lines on logger `personal_ai.audit` (`audit_event`, `user_id`, `detail`). In Grafana Explore (Loki):

```
{container="personal-ai-app"} |= "audit_event"
```

Events include `auth.sign_in`, `auth.sign_out`, `account.export`, `account.delete`, `conversation.delete`, `documents.ingest`, `admin.user.update`, `admin.invite.create`. The provisioned **App logs** dashboard has an Audit panel (`|= "audit_event"`).

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
ADMIN_EMAILS=you@example.com
AUTH_SIGNUP_MODE=invite
SETTINGS_SECRET_KEY=<long-random-secret>
CORS_ORIGINS=https://app.cura-i.com,https://admin.cura-i.com
CADDY_ADMIN_DOMAIN=admin.cura-i.com
```

3. **Google Cloud Console** → OAuth client → **Authorized JavaScript origins** must list the exact URL users open (scheme + host + port), e.g. `https://app.cura-i.com` and `https://admin.cura-i.com`. A mismatch causes the button to fail silently or with `origin_mismatch`.

4. **`AUTH_DISABLED=true`** (default) bypasses login entirely — OAuth will appear “broken” if you expected a login screen.

5. After changing `.env.cloud`, rebuild the app container (`compose up -d --build`) so env vars reload.

6. **Admin portal** — see [admin-portal.md](../admin-portal.md). Staff sign in at `https://admin.cura-i.com` (same Google OAuth). Invite-only signup is the default; promote yourself via `ADMIN_EMAILS`.

## Remote inference (MacBook + Mac Mini)

When using `make up-remote` (see [compose-profiles.md](../compose-profiles.md)):

| Service | Current dev host | Port |
|---------|------------------|------|
| LM Studio (chat) | `192.168.10.1` | 1234 |
| Ollama (embeddings) | `192.168.10.1` | 11434 |
| Docker app (MacBook) | `localhost` | 8000 |

```bash
# From MacBook — verify Mac Mini
curl http://192.168.10.1:1234/v1/models
curl http://192.168.10.1:11434/api/tags

# From app container
docker compose -f docker-compose.yml -f docker-compose.remote-inference.yml \
  --env-file .env.remote exec app curl -s http://192.168.10.1:1234/v1/models

# Restart after .env.remote changes
docker compose -f docker-compose.yml -f docker-compose.remote-inference.yml \
  --env-file .env.remote up -d app
```

**Model:** `qwen-3-14b-instruct` (Q4_K_M). Keep only one chat model loaded in LM Studio.

## Smoke and stress testing

| Script | Purpose |
|--------|---------|
| `./scripts/real_api_smoke.sh` | Health, ready, live FX/weather |
| `./scripts/model_accuracy_smoke.sh` | LLM accuracy probes |
| `./scripts/model_stress_test.py` | Concurrent `/chat` load |
| `./scripts/verify_prod_auth.sh` | OAuth diagnostics |

```bash
make real-api-smoke
make model-stress-local
AUTH_EMAIL=stress-test@example.com make model-stress-prod
APP_URL=https://app.cura-i.com ./scripts/verify_prod_auth.sh
```

Recorded results: [model-stress-testing.md](../model-stress-testing.md), [results/](../results/).

### Per-message latency in UI

Assistant responses show `latency_ms` next to copy/feedback buttons when the backend persists it in message metadata. Redeploy the app container after backend changes for prod.

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
cd frontend && npm run test:capacitor   # mobile drawer, user menu theme
cd frontend && npm run test:visual

make real-api-smoke
make model-stress-local                 # optional: remote inference load test
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