# Production Smoke Checks

The optional **Production Smoke** GitHub Actions workflow checks the deployed application independently of local CI.

## Coverage

Every scheduled or manual run checks:

- app shell loads over HTTPS
- `/health` and `/ready` return HTTP 200
- `/auth/config` has the expected public configuration

Optional authenticated checks validate:

- the test token with `/auth/me`
- a small direct-chat request
- a small document-ingest request

Chat and ingest mutate the test account and can consume provider tokens, so they are disabled by default.

## Run locally

```bash
APP_URL=https://app.cura-i.com ./scripts/prod_smoke.sh
```

With a dedicated test account token:

```bash
APP_URL=https://app.cura-i.com \
PROD_SMOKE_AUTH_TOKEN='replace-me' \
RUN_AUTHENTICATED=true \
./scripts/prod_smoke.sh
```

Add `RUN_MUTATIONS=true` to exercise chat and upload.

## Deep smoke (your user JWT)

Prod disables `POST /auth/token` email minting. Use your Google session JWT for a full workflow matrix:

1. Sign in at https://app.cura-i.com
2. DevTools → Application → Local Storage → `personal-ai-auth-token`
3. Run:

```bash
export AUTH_TOKEN='paste-jwt-here'
APP_URL=https://app.cura-i.com ./scripts/prod_deep_smoke.sh
# or:
make prod-deep-smoke
```

`PROD_SMOKE_AUTH_TOKEN` is accepted as an alias for `AUTH_TOKEN`.

Deep smoke covers:

| Phase | Checks |
|-------|--------|
| Public | app shell, `/health`, `/ready`, `/auth/config` |
| Auth | `/auth/me`, create conversation titled `PROD_DEEP_SMOKE …` |
| Chat paths | `/chat` with `force_strategy` fast / tools / orchestrated |
| Smart | `/smart_chat` greeting + heavier prompt |
| Stream | `/chat/stream` SSE final event |
| Workflow | `/workflow_chat` light prompt |

**Mutations:** creates a conversation and several messages under **your** account and consumes provider tokens. Prefer a dedicated low-privilege test user when possible; an admin account is fine for ad-hoc checks. JWT expires with the normal session lifetime.

Do **not** schedule deep smoke in GitHub Actions nightly (cost + personal tokens). Keep Actions on the light [`scripts/prod_smoke.sh`](../../scripts/prod_smoke.sh) workflow.

## GitHub configuration

Repository settings → **Secrets and variables → Actions**:

| Name | Type | Purpose |
|------|------|---------|
| `PROD_APP_URL` | Variable, optional | Override `https://app.cura-i.com` |
| `PROD_SMOKE_AUTH_TOKEN` | Secret, optional | Bearer token for a dedicated smoke-test account |
| `PROD_SMOKE_AUTHENTICATED` | Variable, optional | Set `true` to run `/auth/me` nightly |
| `PROD_SMOKE_MUTATIONS` | Variable, optional | Set `true` to run chat and ingest nightly |

Create the token for a dedicated, low-privilege test account. Do not use an administrator’s token. Rotate it before JWT expiry and immediately if it appears in logs.

The workflow also supports **Actions → Production Smoke → Run workflow**, where the target and optional checks can be selected per run.

## Failure notification

A failed check fails the workflow, writes the target URL to the GitHub Actions job summary, and opens or comments on a **Production smoke failing** issue so a broken deploy is visible without watching Actions. Enable GitHub notification emails for failed Actions runs (GitHub Settings → Notifications → Actions) or connect the repository’s Actions failures to the team’s incident channel.

Use the deployment logs and [ops runbook](./ops-runbook.md) for triage.
