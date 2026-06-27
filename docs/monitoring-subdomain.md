# Grafana HTTPS subdomain (grafana.app.cura-i.com)

Expose Grafana over **HTTPS** with **Grafana login** — no SSH tunnel, no public Prometheus.

| URL | Auth | Notes |
|-----|------|-------|
| `https://grafana.app.cura-i.com` | Grafana (`admin` + password) | Dashboards, Loki logs |
| `https://app.cura-i.com` | App OAuth / API | Unchanged |
| Prometheus `:9090` | **Not public** | Internal Docker network only |

We use **Caddy in Docker** (same pattern as the existing prod `via: Caddy` setup) with automatic Let's Encrypt certificates.

---

## One-time setup

### 1. DNS (at your domain registrar)

Add an **A record** pointing to the VM external IP (`35.254.92.211`):

| Type | Name | Value |
|------|------|-------|
| A | `grafana.app` | `35.254.92.211` |

(`app.cura-i.com` should already point to the same IP.)

Verify:

```bash
dig +short grafana.app.cura-i.com
# → 35.254.92.211
```

### 2. `.env.cloud` on the VM

Add to `/opt/personal-ai/.env.cloud`:

```bash
CADDY_APP_DOMAIN=app.cura-i.com
CADDY_GRAFANA_DOMAIN=grafana.app.cura-i.com
CADDY_ACME_EMAIL=your-email@example.com

GRAFANA_ROOT_URL=https://grafana.app.cura-i.com
GRAFANA_DOMAIN=grafana.app.cura-i.com
GRAFANA_ADMIN_PASSWORD=your-strong-password-here
```

### 3. On the VM

```bash
cd /opt/personal-ai
git pull   # or deploy via CI
chmod +x scripts/setup_grafana_subdomain.sh scripts/deploy_prod.sh
./scripts/setup_grafana_subdomain.sh   # stops host Caddy if it holds :443
./scripts/deploy_prod.sh
```

### 4. Open Grafana

- URL: **https://grafana.app.cura-i.com**
- User: `admin`
- Password: `GRAFANA_ADMIN_PASSWORD` from `.env.cloud`

---

## How it works

```
Browser → Caddy (:443, TLS) → grafana:3000 (Docker network)
                            → app:8000     (app.cura-i.com)
Prometheus stays on 127.0.0.1:9090 — reachable only from Grafana datasource.
```

Files:

- `monitoring/caddy/Caddyfile` — Caddy routes
- `docker-compose.caddy.yml` — Caddy service + localhost-only binds for app/grafana/prometheus

`deploy_prod.sh` automatically adds `-f docker-compose.caddy.yml` when `CADDY_APP_DOMAIN` is set in `.env.cloud`.

---

## Day-to-day access

Just open **https://grafana.app.cura-i.com** in a browser and log in. No SSH tunnel needed.

Optional local fallback (if subdomain is down):

```bash
ssh -L 3000:localhost:3000 YOUR_USER@35.254.92.211
open http://localhost:3000
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Certificate error | Wait for DNS propagation; check `CADDY_ACME_EMAIL` |
| `address already in use` on :443 | Run `./scripts/setup_grafana_subdomain.sh` to stop host Caddy |
| Grafana login loop | Set `GRAFANA_ROOT_URL` / `GRAFANA_DOMAIN` to match subdomain; redeploy |
| No data in dashboards | `docker logs personal-ai-prometheus`; check datasource `http://prometheus:9090` |
| App down after enable | Caddy now fronts app — check `docker logs personal-ai-caddy` |

```bash
docker logs --tail=80 personal-ai-caddy
docker logs --tail=80 personal-ai-grafana
curl -fsS https://grafana.app.cura-i.com/api/health
curl -fsS https://app.cura-i.com/health
```

---

## Why not Grafana Cloud?

Grafana Cloud is a separate hosted product. This stack uses **self-hosted** Prometheus + Loki + Grafana in Docker. Moving to Grafana Cloud would require exporting metrics/logs to their SaaS — a larger migration. The subdomain approach keeps your existing dashboards with minimal change.

---

## Security notes

- Change `GRAFANA_ADMIN_PASSWORD` from the default.
- Prometheus is **not** exposed on the public internet.
- Grafana sign-up is disabled (`GF_USERS_ALLOW_SIGN_UP=false`).
- Consider IP allowlisting at GCP firewall if you want to restrict who can reach `:443`.
