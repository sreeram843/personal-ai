# Production GCP VM (CurAI)

End-to-end path from a fresh GCP VM to HTTPS CurAI at `app.cura-i.com` (and optional `admin` / `grafana` subdomains).

## Prerequisites

- Debian/Ubuntu VM with Docker + Docker Compose plugin
- External static IP
- DNS A records:
  - `app.cura-i.com` → VM IP
  - `admin.cura-i.com` → VM IP (optional admin portal)
  - `grafana.app.cura-i.com` → VM IP (optional monitoring)

## 1. Firewall

Open **80** and **443** to the world. Do **not** expose Postgres (5432), Qdrant (6333), Redis (6379), Grafana (3000), Prometheus (9090), or Loki (3100) publicly.

```bash
# Example gcloud (adjust network/tags for your project)
gcloud compute firewall-rules create curai-https \
  --allow=tcp:80,tcp:443 \
  --target-tags=curai-vm \
  --source-ranges=0.0.0.0/0
```

## 2. Clone and env

```bash
git clone https://github.com/sreeram843/personal-ai.git
cd personal-ai
cp .env.cloud.example .env.cloud
```

Fill at least:

| Variable | Notes |
|----------|--------|
| `LLM_CLOUD_*` | Cold-start OpenAI-compatible fallback (or manage providers in Admin later) |
| `AUTH_DISABLED=false` | Required for real Google login |
| `GOOGLE_CLIENT_ID` | Web client ID from Google Cloud |
| `JWT_SECRET` | Long random (≥32 chars) |
| `SETTINGS_SECRET_KEY` | Separate Fernet key for encrypted provider secrets |
| `ADMIN_EMAILS` | Your email for first admin |
| `CORS_ORIGINS` | `https://app.cura-i.com,https://admin.cura-i.com` (no wildcard, no raw IP in prod) |
| `CADDY_APP_DOMAIN` / `CADDY_ADMIN_DOMAIN` / `CADDY_GRAFANA_DOMAIN` | Public hostnames |
| `CADDY_ACME_EMAIL` | Let's Encrypt contact |
| `GRAFANA_ADMIN_PASSWORD` | **Not** `admin` |
| `PRIVACY_POLICY_URL` / `TERMS_OF_SERVICE_URL` | Optional; shown on login + OAuth consent |

## 3. Google OAuth Console checklist

1. [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials) → OAuth 2.0 **Web application** client
2. **Authorized JavaScript origins** (exact):
   - `https://app.cura-i.com`
   - `https://admin.cura-i.com`
3. Redirect URIs are not required for `@react-oauth/google` button / One Tap
4. [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent):
   - App name, support email, privacy/terms links
   - Publishing status **In production** for public sign-in (or Testing + Test users for private beta)
5. Redeploy after changing `.env.cloud`

## 4. Caddy HTTPS

Production uses the Docker Caddy overlay (`docker-compose.caddy.yml` + `monitoring/caddy/Caddyfile`), not a host-installed Caddy by default.

```bash
# Optional helper that prints the compose command / DNS reminders:
./scripts/setup_caddy.sh
```

Deploy stack:

```bash
./scripts/deploy_prod.sh
# or manually:
docker compose --env-file .env.cloud -f docker-compose.yml -f docker-compose.cloud.yml -f docker-compose.caddy.yml up -d --build
```

## 5. Verify

```bash
APP_URL=https://app.cura-i.com ./scripts/verify_prod.sh
APP_URL=https://app.cura-i.com ./scripts/verify_prod_auth.sh
```

Expect `/health` and `/ready` 200, HTTPS OK, and Google auth enabled when `AUTH_DISABLED=false`.

## Related docs

- [ops-runbook.md](./ops-runbook.md) — day-2 operations
- [admin-portal.md](./admin-portal.md) — admin host + invites
- [monitoring-subdomain.md](./monitoring-subdomain.md) — Grafana HTTPS
- [deployment-checklist.md](./deployment-checklist.md) — release checklist
