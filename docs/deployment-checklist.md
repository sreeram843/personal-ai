# Deployment Checklist

## Configuration

- [ ] `.env` is populated for the target environment.
- [ ] `CORS_ORIGINS` only includes required origins.
- [ ] `GRAFANA_ADMIN_PASSWORD` is overridden from the default.
- [ ] Optional framework flags are set intentionally.
- [ ] Ollama and Qdrant endpoints are correct for the target environment.

## Security

- [ ] `python scripts/security_checks.py` passes.
- [ ] No secrets are committed to tracked files.
- [ ] Production configs do not use wildcard CORS.
- [ ] Observability credentials are not hardcoded in compose or workflow files.

## Application Validation

- [ ] `python -m pytest` passes.
- [ ] `cd frontend && npm run build` passes.
- [ ] `cd frontend && npm run test:e2e` passes.
- [ ] `cd frontend && npm run test:visual` passes.
- [ ] `./scripts/quality_gate.sh` passes end to end.

## Containers and Infra

- [ ] `docker compose config` validates.
- [ ] `docker build -f Dockerfile.backend .` succeeds.
- [ ] Ollama models are present.
- [ ] Qdrant storage is writable and reachable.
- [ ] Redis is reachable when adapter caching is enabled.
- [ ] Prometheus can scrape the app.
- [ ] Grafana datasource health is `OK`.

## Smoke Tests

- [ ] Standard chat works.
- [ ] RAG chat returns sources after ingesting a document.
- [ ] Live FX or weather query returns verified provenance.
- [ ] Metrics endpoint returns Prometheus text output.
- [ ] UI mode switching and uploads work in the browser.

## Release Notes

- [ ] README and docs reflect the shipped behavior.
- [ ] Known limitations are documented.
- [ ] Rollback plan is identified.