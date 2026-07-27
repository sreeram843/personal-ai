# Deployment

## Production (GCP VM) — primary path

Public chat: **https://app.cura-i.com**  
Admin: **https://admin.cura-i.com**  
Grafana (optional): **https://grafana.app.cura-i.com**

Canonical guide: in-repo **`docs/prod-gcp-vm.md`** (DNS, firewall, OAuth, Caddy, verify).

### Deploy on the VM

```bash
cd /opt/personal-ai
./scripts/setup_caddy.sh    # validates CADDY_* + prints compose command
./scripts/deploy_prod.sh    # or: make deploy-prod
```

Typical steps inside deploy: compose up --build, pull embed model, migrate DB, `./scripts/verify_prod.sh`.

Env file on server: **`.env.cloud`**.

### Checklist before go-live

- [ ] DNS A records for app + admin (+ grafana if used)
- [ ] Firewall allows 80/443
- [ ] Google OAuth origins match HTTPS hosts
- [ ] `ADMIN_EMAILS`, `SETTINGS_SECRET_KEY`, `CORS_ORIGINS`
- [ ] `alembic` / migrations applied
- [ ] `verify_prod.sh` green (`/health`, `/ready`, HTTPS, auth)

## Other targets

| Target | Docs |
|--------|------|
| AWS | See `docs/` deploy/AWS notes in repo |
| GPU / vLLM | `.env.gpu-vllm.example`, GPU compose |
| Helm / Terraform | Phase 2/3 artifacts under `docs/` / infra folders |

## Monitoring subdomain

See `docs/monitoring-subdomain.md` for Grafana HTTPS via Caddy.

## Related

- [Operations](Operations) — backup/restore
- [Authentication](Authentication)
- [Admin Portal](Admin-Portal)
- [Troubleshooting](Troubleshooting)
