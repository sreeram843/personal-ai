# Troubleshooting

## `/ready` failing

- Qdrant down or wrong `QDRANT_URL`
- Ollama down or embed/chat model not pulled
- Check `docker compose ps` and `curl` health endpoints in [Operations](Operations)

## Embed / dimension errors

- `EMBEDDING_DIMENSION` must match the embed model (768 for `nomic-embed-text`)
- Changing embed models requires re-ingest

## PDF upload fails

- Confirm `.pdf` in `INGEST_ALLOWED_EXTENSIONS`
- Raise `INGEST_MAX_UPLOAD_BYTES` for large binaries
- Check backend logs for pypdf extract errors

## Auth / Google login loops

- `AUTH_DISABLED` mismatch between env and expectation
- OAuth client origins missing `https://app.cura-i.com` or admin host
- `CORS_ORIGINS` missing the browser origin
- Invite mode without invite and email not in `ADMIN_EMAILS`

## Admin 403

- User role is `user` only — need `admin` or `support`
- Confirm `ADMIN_EMAILS` promotion on first Google login

## Live data always guardrailed

- Intent not classified as live
- Upstream FX/weather/search failures
- Check Redis cache / adapter logs; see [Live Data](Live-Data)

## Empty RAG answers / missing citations

- Nothing ingested for that user
- Hybrid/rerank misconfig
- Writer dropping markers — citations service should preserve them; check recent chat path

## Playwright / frontend native deps (macOS)

Running Linux Playwright images can break `@rollup/rollup-darwin-arm64`. Reinstall frontend `node_modules` for the host platform.

## Compose / Caddy TLS

- Run `./scripts/setup_caddy.sh` and read validation errors
- DNS must point at the VM before ACME succeeds

## Still stuck

1. `docs/ops-runbook.md`
2. Grafana/Loki if enabled
3. `GET /metrics` and app container logs
