#!/usr/bin/env bash
# Restore Postgres + Qdrant volumes from a backup_prod.sh snapshot.
#
# Usage (on the server, after deploy_prod.sh has created empty volumes):
#   cd /opt/personal-ai
#   ./scripts/restore_prod.sh backups/<UTC-stamp>
#   BACKUP_DIR=/var/backups/personal-ai ./scripts/restore_prod.sh <stamp-or-path>
#   RESTORE_CONFIRM=1 ./scripts/restore_prod.sh backups/<UTC-stamp>
#
# Backup: ./scripts/backup_prod.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${DEPLOY_ENV_FILE:-$ROOT_DIR/.env.cloud}"
BACKUP_ROOT="${BACKUP_DIR:-$ROOT_DIR/backups}"

cd "$ROOT_DIR"

usage() {
  printf 'Usage: %s <stamp-or-path>\n' "$(basename "$0")" >&2
  printf '   or: BACKUP_DIR=/var/backups/personal-ai %s <stamp>\n' "$(basename "$0")" >&2
  exit 1
}

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

resolve_backup_dir() {
  local arg="$1"
  local candidate

  if [ -d "$arg" ]; then
    (cd "$arg" && pwd)
    return 0
  fi

  # Bare stamp (no slashes) under BACKUP_DIR / default backups/
  if [ "$arg" = "${arg##*/}" ]; then
    candidate="${BACKUP_ROOT}/${arg}"
    if [ -d "$candidate" ]; then
      (cd "$candidate" && pwd)
      return 0
    fi
  fi

  candidate="${ROOT_DIR}/${arg}"
  if [ -d "$candidate" ]; then
    (cd "$candidate" && pwd)
    return 0
  fi

  printf 'ERROR: backup directory not found: %s\n' "$arg" >&2
  exit 1
}

if [ "${1:-}" = "" ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
fi

SRC_DIR="$(resolve_backup_dir "$1")"
PG_DUMP="${SRC_DIR}/postgres.sql.gz"
QDRANT_TAR="${SRC_DIR}/qdrant_storage.tar.gz"
PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-personal_ai}"

if [ ! -f "$PG_DUMP" ]; then
  printf 'ERROR: required dump missing: %s\n' "$PG_DUMP" >&2
  exit 1
fi

if [ "${RESTORE_CONFIRM:-}" != "1" ]; then
  if [ -t 0 ]; then
    printf 'This will OVERWRITE live Postgres (and Qdrant if a tarball is present) from:\n  %s\n' "$SRC_DIR"
    printf 'Type RESTORE to continue: '
    read -r answer
    if [ "$answer" != "RESTORE" ]; then
      printf 'Aborted.\n' >&2
      exit 1
    fi
  else
    printf 'ERROR: stdin is not a TTY. Re-run with RESTORE_CONFIRM=1 to restore without a prompt.\n' >&2
    exit 1
  fi
fi

if ! compose exec -T postgres pg_isready -U "$PGUSER" >/dev/null 2>&1; then
  printf 'ERROR: Postgres is not ready. Run ./scripts/deploy_prod.sh first so volumes exist.\n' >&2
  exit 1
fi

# pg_dump is schema+data without --clean; recreate the DB so a post-migrate volume accepts it.
printf 'Recreating database %s for restore\n' "$PGDB"
compose exec -T postgres dropdb -U "$PGUSER" --if-exists --force "$PGDB"
compose exec -T postgres createdb -U "$PGUSER" "$PGDB"

printf 'Restoring Postgres from %s\n' "$PG_DUMP"
gunzip -c "$PG_DUMP" | compose exec -T postgres psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 >/dev/null

if [ -f "$QDRANT_TAR" ]; then
  PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$ROOT_DIR")}"
  QDRANT_VOLUME="${PROJECT_NAME}_qdrant_storage"
  if ! docker volume inspect "$QDRANT_VOLUME" >/dev/null 2>&1; then
    printf 'ERROR: Qdrant tarball present but volume %s not found. Run ./scripts/deploy_prod.sh first.\n' \
      "$QDRANT_VOLUME" >&2
    exit 1
  fi

  printf 'Restoring Qdrant volume %s from %s\n' "$QDRANT_VOLUME" "$QDRANT_TAR"
  compose stop qdrant
  docker run --rm \
    -v "${QDRANT_VOLUME}:/data" \
    -v "${SRC_DIR}:/backup:ro" \
    alpine:3.20 \
    sh -c 'find /data -mindepth 1 -delete && tar -C /data -xzf /backup/qdrant_storage.tar.gz'
  compose start qdrant
else
  printf 'WARN: %s not found; skipped Qdrant restore.\n' "$QDRANT_TAR" >&2
fi

printf 'Restore complete: %s\n' "$SRC_DIR"
printf 'Next: verify with ./scripts/verify_prod.sh\n'
