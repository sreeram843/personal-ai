# Operations

## Purpose

Local stack ops, health checks, prod backup/restore, audit logs. Full detail: `docs/ops-runbook.md`.

## Health checks

```bash
docker compose ps
curl -I http://localhost:8000/metrics
curl -I http://localhost:6333/collections
curl -s http://localhost:11434/api/tags
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

Prod verify:

```bash
./scripts/verify_prod.sh
```

## Backup (Postgres + Qdrant)

VM disk loss wipes conversations and embeddings.

```bash
cd /opt/personal-ai
./scripts/backup_prod.sh
# optional: BACKUP_DIR=... BACKUP_RETENTION_DAYS=14 ./scripts/backup_prod.sh
```

Each run under `backups/<UTC-stamp>/`:

- `postgres.sql.gz`
- `qdrant_storage.tar.gz`
- `qdrant-snapshot.json` (best-effort)

Copy off-VM (GCS/S3) and encrypt at rest.

### Restore (sketch)

After deploy creates empty volumes:

1. Restore Postgres via `psql` into the compose Postgres service  
2. Stop Qdrant, replace volume from tar, start Qdrant  

Exact commands: `docs/ops-runbook.md`. Confirm volume name with `docker volume ls | grep qdrant`.

## Audit events (Loki)

Sensitive actions → logger `personal_ai.audit` (`audit_event`, `user_id`, `detail`). Query in Grafana Explore (Loki).

## Dashboards

- Grafana: http://localhost:3000 (local) or https://grafana.app.cura-i.com
- App Logs dashboard when Loki profile is up

## Related

- [Deployment](Deployment)
- [Troubleshooting](Troubleshooting)
- [Compose Profiles](Compose-Profiles)
