#!/usr/bin/env bash
# Production deploy for cloud-chat + workers (GCP VM, manual SSH, or CI).
#
# Usage (on the server):
#   cd /opt/personal-ai
#   ./scripts/deploy_prod.sh
#
# Requires .env.cloud in the repo root (see .env.cloud.example).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${DEPLOY_ENV_FILE:-$ROOT_DIR/.env.cloud}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
OLLAMA_URL="${OLLAMA_HEALTH_URL:-http://127.0.0.1:11434}"

cd "$ROOT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  printf 'ERROR: %s not found. Copy .env.cloud.example and configure your cloud API keys.\n' "$ENV_FILE" >&2
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

stop_host_caddy_if_needed() {
  if [ -z "${CADDY_APP_DOMAIN:-}" ]; then
    return 0
  fi
  printf '\n[%s] Ensuring host ports 80/443 are free for Docker Caddy\n' "$(date '+%H:%M:%S')"
  if systemctl is-active --quiet caddy 2>/dev/null; then
    printf 'Stopping system Caddy service...\n'
    sudo systemctl stop caddy
    sudo systemctl disable caddy
  fi
  if command -v ss >/dev/null 2>&1; then
    if ss -tln | grep -qE ':80 |:443 '; then
      printf 'WARN: Something still listens on 80/443:\n'
      ss -tlnp | grep -E ':80 |:443 ' || true
      printf 'Stop it before Docker Caddy can start (e.g. sudo systemctl stop caddy nginx apache2).\n'
    fi
  fi
}

printf '\n[%s] Pulling latest code (optional — skip if CI already synced)\n' "$(date '+%H:%M:%S')"
if [ "${DEPLOY_SKIP_GIT:-0}" != "1" ] && [ -d .git ]; then
  git fetch origin main
  git reset --hard origin/main
fi

printf '\n[%s] Building and starting stack\n' "$(date '+%H:%M:%S')"
stop_host_caddy_if_needed
compose up -d --build

printf '\n[%s] Waiting for Ollama (embeddings)\n' "$(date '+%H:%M:%S')"
for attempt in {1..30}; do
  if curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    printf 'ERROR: Ollama did not become ready at %s\n' "$OLLAMA_URL" >&2
    compose ps
    exit 1
  fi
  sleep 2
done

printf '\n[%s] Ensuring embedding model: %s\n' "$(date '+%H:%M:%S')" "$EMBED_MODEL"
compose exec -T ollama ollama pull "$EMBED_MODEL"

printf '\n[%s] Verifying Ollama embed endpoint\n' "$(date '+%H:%M:%S')"
curl -fsS -X POST "$OLLAMA_URL/api/embed" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$EMBED_MODEL\",\"input\":[\"deploy smoke\"]}" >/dev/null

printf '\n[%s] Running database migrations\n' "$(date '+%H:%M:%S')"
compose exec -T app alembic upgrade head

printf '\n[%s] Ensuring Qdrant vector collection\n' "$(date '+%H:%M:%S')"
compose exec -T app python -c "from app.core.deps import get_vector_store; get_vector_store().ensure_collection()"

printf '\n[%s] Health checks\n' "$(date '+%H:%M:%S')"
if [ -n "${CADDY_APP_DOMAIN:-}" ]; then
  curl -fsS "https://${CADDY_APP_DOMAIN}/health"
  curl -fsS "https://${CADDY_APP_DOMAIN}/ready"
  if [ -n "${CADDY_GRAFANA_DOMAIN:-}" ]; then
    curl -fsS "https://${CADDY_GRAFANA_DOMAIN}/api/health"
  fi
else
  curl -fsS http://127.0.0.1:8000/health
  curl -fsS http://127.0.0.1:8000/ready
fi

printf '\n[%s] Post-deploy smoke checks\n' "$(date '+%H:%M:%S')"
chmod +x scripts/verify_prod.sh scripts/verify_prod_auth.sh
if [ -n "${CADDY_APP_DOMAIN:-}" ]; then
  APP_URL="https://${CADDY_APP_DOMAIN}" ./scripts/verify_prod.sh
else
  APP_URL=http://127.0.0.1:8000 ./scripts/verify_prod.sh
fi

printf '\n[%s] Deploy complete\n' "$(date '+%H:%M:%S')"
compose ps
