#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
QDRANT_URL="http://127.0.0.1:6333/collections"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

printf '\n[%s] Starting smoke services (qdrant + redis)\n' "$(date '+%H:%M:%S')"
docker compose -f "$COMPOSE_FILE" up -d qdrant redis >/dev/null

printf '[%s] Probing qdrant readiness\n' "$(date '+%H:%M:%S')"
for attempt in {1..30}; do
  if curl -fsS "$QDRANT_URL" >/dev/null; then
    printf '[%s] Compose smoke test passed\n' "$(date '+%H:%M:%S')"
    exit 0
  fi
  sleep 2
done

printf '[%s] Compose smoke test failed: qdrant did not become ready in time\n' "$(date '+%H:%M:%S')" >&2
exit 1
