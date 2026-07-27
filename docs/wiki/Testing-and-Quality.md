# Testing and Quality

## Quality gate

Primary one-shot check used before merge:

```bash
make quality-gate
# or scripts used by CI / Makefile targets
```

Typically covers backend tests, frontend checks, and Playwright where configured.

## Backend (pytest)

```bash
source .venv/bin/activate   # if local
pytest
```

Notable suites:

- Multi-provider gateway
- Retrieval accuracy / golden set (`tests/fixtures/retrieval_golden.json`)
- Live data / routing guards
- Auth and admin APIs

## Frontend

```bash
cd frontend
npm test          # if configured
npm run build
npx playwright test
```

Update Linux mobile snapshots carefully when UI changes; avoid breaking darwin optional deps when running Linux Playwright locally (reinstall platform rollup packages if needed).

## Manual prod checklist

For https://app.cura-i.com — exercise:

- Login / invite gate
- Chat streaming
- Document upload (txt/md/pdf)
- Sources / citations on RAG answers
- Live weather / FX
- Admin providers + routing (staff)

## Related

- [RAG and Retrieval](RAG-and-Retrieval) — recall@k / MRR
- [Troubleshooting](Troubleshooting)
- In-repo: `docs/testing.md` if present
