#!/usr/bin/env bash
# Backup Postgres + Qdrant volumes for cloud-chat VM deploy.
#
# Usage (on the server):
#   cd /opt/personal-ai
#   ./scripts/backup_prod.sh
#   BACKUP_DIR=/var/backups/personal-ai ./scripts/backup_prod.sh
#
# Restore: ./scripts/restore_prod.sh backups/<UTC-stamp>
# Restore notes: docs/runbooks/ops-runbook.md (Backup and restore)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${DEPLOY_ENV_FILE:-$ROOT_DIR/.env.cloud}"
BACKUP_ROOT="${BACKUP_DIR:-$ROOT_DIR/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${BACKUP_ROOT}/${STAMP}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

cd "$ROOT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  printf 'ERROR: %s not found.\n' "$ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.cloud.yml)
if [ -n "${CADDY_APP_DOMAIN:-}" ]; then
  COMPOSE_FILES+=(-f docker-compose.caddy.yml)
fi

compose() {
  docker compose \
    --profile cloud-chat --profile workers \
    "${COMPOSE_FILES[@]}" \
    --env-file "$ENV_FILE" \
    "$@"
}

mkdir -p "$OUT_DIR"

printf 'Backing up Postgres to %s/postgres.sql.gz\n' "$OUT_DIR"
compose exec -T postgres pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-personal_ai}" \
  | gzip -c > "${OUT_DIR}/postgres.sql.gz"

printf 'Creating Qdrant snapshot via API (best-effort) and volume tarball\n'
QDRANT_URL="${QDRANT_BACKUP_URL:-http://127.0.0.1:6333}"
if curl -fsS -X POST "${QDRANT_URL}/collections/personal_ai_documents/snapshots" -o "${OUT_DIR}/qdrant-snapshot.json" 2>/dev/null; then
  :
else
  printf 'WARN: Qdrant snapshot API unavailable; continuing with volume copy.\n' >&2
fi

# Named volume from compose project (default project name = directory basename).
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$ROOT_DIR")}"
QDRANT_VOLUME="${PROJECT_NAME}_qdrant_storage"
if docker volume inspect "$QDRANT_VOLUME" >/dev/null 2>&1; then
  docker run --rm \
    -v "${QDRANT_VOLUME}:/data:ro" \
    -v "${OUT_DIR}:/backup" \
    alpine:3.20 \
    tar -C /data -czf /backup/qdrant_storage.tar.gz .
else
  printf 'WARN: volume %s not found; skipped Qdrant tarball.\n' "$QDRANT_VOLUME" >&2
fi

printf '%s\n' "$STAMP" > "${OUT_DIR}/BACKUP_ID"
cat > "${OUT_DIR}/README.txt" <<EOF
Personal AI backup ${STAMP}
- postgres.sql.gz : pg_dump of personal_ai
- qdrant_storage.tar.gz : Qdrant storage volume (if present)
- qdrant-snapshot.json : API snapshot metadata (if present)

Restore: see docs/runbooks/ops-runbook.md
EOF

if command -v find >/dev/null 2>&1; then
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} +
fi

printf 'Backup complete: %s\n' "$OUT_DIR"
