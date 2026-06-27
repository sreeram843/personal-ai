#!/usr/bin/env bash
# One-time prep on the prod VM before enabling grafana.app.cura-i.com via Caddy.
#
# Run on the server:
#   cd /opt/personal-ai
#   ./scripts/setup_grafana_subdomain.sh
#
# Prerequisites (at your DNS provider):
#   A  grafana.app.cura-i.com  →  VM external IP (same as app.cura-i.com)
#   A  app.cura-i.com          →  VM external IP (if not already set)
#
# Then add to .env.cloud (see .env.cloud.example) and run ./scripts/deploy_prod.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${DEPLOY_ENV_FILE:-$ROOT_DIR/.env.cloud}"

cd "$ROOT_DIR"

printf '\n=== Grafana subdomain setup ===\n\n'

if [ ! -f "$ENV_FILE" ]; then
  printf 'ERROR: %s not found.\n' "$ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

GRAFANA_DOMAIN="${CADDY_GRAFANA_DOMAIN:-grafana.app.cura-i.com}"
APP_DOMAIN="${CADDY_APP_DOMAIN:-app.cura-i.com}"

printf 'Target domains:\n  App:     %s\n  Grafana: %s\n\n' "$APP_DOMAIN" "$GRAFANA_DOMAIN"

if [ -z "${CADDY_ACME_EMAIL:-}" ]; then
  printf 'WARN: CADDY_ACME_EMAIL is not set in %s (Let''s Encrypt contact).\n' "$ENV_FILE"
fi

if [ -z "${CADDY_APP_DOMAIN:-}" ]; then
  printf 'WARN: CADDY_APP_DOMAIN is not set — deploy_prod.sh will not load docker-compose.caddy.yml.\n'
fi

printf 'Checking for processes on ports 80/443...\n'
if command -v ss >/dev/null 2>&1; then
  ss -tlnp | grep -E ':80 |:443 ' || true
fi

if systemctl is-active --quiet caddy 2>/dev/null; then
  printf '\nStopping system Caddy (Docker Caddy will take over 80/443)...\n'
  sudo systemctl stop caddy
  sudo systemctl disable caddy
  printf 'System Caddy disabled.\n'
else
  printf 'No active system Caddy service found.\n'
fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx personal-ai-caddy; then
  printf 'Docker Caddy container already running.\n'
else
  printf 'Docker Caddy not running yet — run ./scripts/deploy_prod.sh after DNS propagates.\n'
fi

printf '\nDNS check (from this VM):\n'
VM_IP="$(curl -fsS -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || true)"
if [ -n "$VM_IP" ]; then
  printf '  VM external IP: %s\n' "$VM_IP"
  for host in "$APP_DOMAIN" "$GRAFANA_DOMAIN"; do
    resolved="$(getent ahostsv4 "$host" 2>/dev/null | awk 'NR==1{print $1}' || true)"
    if [ "$resolved" = "$VM_IP" ]; then
      printf '  OK  %s → %s\n' "$host" "$resolved"
    elif [ -n "$resolved" ]; then
      printf '  WARN %s → %s (expected %s)\n' "$host" "$resolved" "$VM_IP"
    else
      printf '  WARN %s did not resolve yet\n' "$host"
    fi
  done
else
  printf '  (not on GCP metadata — verify DNS manually)\n'
fi

printf '\nNext steps:\n'
printf '  1. Ensure .env.cloud has CADDY_* and GRAFANA_* vars (see .env.cloud.example)\n'
printf '  2. Set a strong GRAFANA_ADMIN_PASSWORD in .env.cloud\n'
printf '  3. ./scripts/deploy_prod.sh\n'
printf '  4. Open https://%s/ (login: admin + GRAFANA_ADMIN_PASSWORD)\n\n' "$GRAFANA_DOMAIN"
