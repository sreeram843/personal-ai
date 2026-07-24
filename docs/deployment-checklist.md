# Deployment Checklist

## Configuration

- [ ] `.env` / `.env.cloud` is populated for the target environment.
- [ ] `JWT_SECRET` is a long random value (not the repo default).
- [ ] `SETTINGS_SECRET_KEY` is set for encrypted Admin provider secrets.
- [ ] `CORS_ORIGINS` only includes required origins (prod: HTTPS app/admin hosts; no `*` / no raw IP).
- [ ] `GRAFANA_ADMIN_PASSWORD` is overridden from the default `admin`.
- [ ] Optional framework flags are set intentionally.
- [ ] Ollama and Qdrant endpoints are correct for the target environment.
- [ ] `PRIVACY_POLICY_URL` / `TERMS_OF_SERVICE_URL` set if publishing Google OAuth publicly.

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
- [ ] Unified chat and document uploads work in the browser (`POST /chat/stream`).
- [ ] Assistant messages show response time after completion (when backend deployed).
- [ ] Mobile drawer and account menu theme toggle (`npm run test:capacitor`).
- [ ] `make real-api-smoke` passes.
- [ ] `make model-stress-local` or prod stress with `AUTH_EMAIL` (see [docs/model-stress-testing.md](./model-stress-testing.md)).

## Production-specific

- [ ] Follow [prod-gcp-vm.md](./prod-gcp-vm.md) for first-time VM setup.
- [ ] `https://app.cura-i.com/health` returns 200 (`./scripts/verify_prod.sh`).
- [ ] Google OAuth origins match public URL (`./scripts/verify_prod_auth.sh`).
- [ ] OAuth consent screen is **In production** (or Test users listed).
- [ ] Sequential prod stress passes (`AUTH_EMAIL=stress-test@example.com make model-stress-prod`).
- [ ] `latency_ms` persisted in message metadata after backend deploy.

## Release Notes

- [ ] README and docs reflect the shipped behavior.
- [ ] Known limitations are documented.
- [ ] Rollback plan is identified.