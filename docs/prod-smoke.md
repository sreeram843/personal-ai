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

A failed check fails the workflow and writes the target URL to the GitHub Actions job summary. Enable GitHub notification emails for failed Actions runs (GitHub Settings → Notifications → Actions) or connect the repository’s Actions failures to the team’s incident channel.

Use the deployment logs and [ops runbook](./ops-runbook.md) for triage.
