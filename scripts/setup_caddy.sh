#!/usr/bin/env bash
# Prepare / document Caddy HTTPS for CurAI on the prod VM.
# Default production path uses Docker Compose + docker-compose.caddy.yml
# (see monitoring/caddy/Caddyfile). This script validates env and prints next steps.
#
# Usage (on the VM, from repo root):
#   ./scripts/setup_caddy.sh
#   ENV_FILE=.env.cloud ./scripts/setup_caddy.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.cloud}"

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing %s — copy .env.cloud.example and fill CADDY_* / ACME email.\n' "$ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

: "${CADDY_APP_DOMAIN:?Set CADDY_APP_DOMAIN in $ENV_FILE}"
: "${CADDY_ACME_EMAIL:?Set CADDY_ACME_EMAIL in $ENV_FILE}"

printf 'Caddy (Docker) setup for CurAI\n'
printf '  App domain:     %s\n' "$CADDY_APP_DOMAIN"
printf '  Admin domain:   %s\n' "${CADDY_ADMIN_DOMAIN:-"(unset)"}"
printf '  Grafana domain: %s\n' "${CADDY_GRAFANA_DOMAIN:-"(unset)"}"
printf '  ACME email:     %s\n' "$CADDY_ACME_EMAIL"
printf '\nDNS: point A records for those hosts to this VM public IP.\n'
printf 'Firewall: allow tcp/80 and tcp/443 only for the public edge.\n'
printf '\nStart / refresh HTTPS stack:\n'
printf '  docker compose --env-file %s -f docker-compose.yml -f docker-compose.cloud.yml -f docker-compose.caddy.yml up -d\n' "$ENV_FILE"
printf '\nOr: ./scripts/deploy_prod.sh\n'
printf 'Caddyfile: monitoring/caddy/Caddyfile\n'
printf 'Docs: docs/prod-gcp-vm.md\n'
