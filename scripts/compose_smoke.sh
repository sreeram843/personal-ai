#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
SMOKE_OVERRIDE="$ROOT_DIR/docker-compose.smoke.yml"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-personal-ai}"
NETWORK_NAME="${PROJECT_NAME}_personal-ai-network"

cleanup() {
  docker compose --profile local -f "$COMPOSE_FILE" -f "$SMOKE_OVERRIDE" down --remove-orphans >/dev/null 2>&1 || true
  rm -f "$SMOKE_OVERRIDE"
}

trap cleanup EXIT

# Avoid publishing host ports so smoke still works when 6333/6379 are already taken
# by another local stack.
cat > "$SMOKE_OVERRIDE" <<'YAML'
services:
  qdrant:
    ports: !override []
  redis:
    ports: !override []
YAML

printf '\n[%s] Starting smoke services (qdrant + redis, no host ports)\n' "$(date '+%H:%M:%S')"
docker compose --profile local -f "$COMPOSE_FILE" -f "$SMOKE_OVERRIDE" up -d qdrant redis >/dev/null

printf '[%s] Probing qdrant readiness\n' "$(date '+%H:%M:%S')"
for attempt in {1..30}; do
  if docker run --rm --network "$NETWORK_NAME" curlimages/curl:8.5.0 \
    -fsS "http://qdrant:6333/collections" >/dev/null 2>&1; then
    printf '[%s] Compose smoke test passed\n' "$(date '+%H:%M:%S')"
    exit 0
  fi
  sleep 2
done

printf '[%s] Compose smoke test failed: qdrant did not become ready in time\n' "$(date '+%H:%M:%S')" >&2
exit 1
