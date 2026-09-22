# 0008 — Opt-in Compose monitoring profile

Status: Accepted

## Context

Prometheus, Loki, Promtail, and Grafana ran as always-on core services
([0006](0006-compose-profiles-for-runtime-switching.md)). On the single-user
production VM that stack used ~760 MB RAM and blocked shrinking below
`e2-medium` (~$25/month compute). The app still exposes `GET /metrics`;
dashboards are unused most of the time.

## Decision

Gate Grafana, Prometheus, Loki, and Promtail behind Compose profile
`monitoring`. Default `make up` / production `deploy_prod.sh` (`cloud-chat` +
`workers`) do not start them. Caddy no longer reverse-proxies
`grafana.app.cura-i.com`. Re-enable locally with `make up-monitoring`; prod
steps are in [monitoring-subdomain.md](../runbooks/monitoring-subdomain.md).

## Consequences

- Production can run on `e2-small` (2 GB) with app, worker, Postgres, Redis,
  Qdrant, Ollama embeddings, and Caddy.
- Live dashboards and Loki log search are off unless the profile is added.
- `/metrics` remains on the app for ad-hoc scrapes.
