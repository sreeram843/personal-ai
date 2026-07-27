# API Reference

Base URL local: `http://localhost:8000`  
Prod: `https://app.cura-i.com`  

Auth: `Authorization: Bearer <JWT>` when `AUTH_DISABLED=false`.

## OpenAI-compatible

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/models` | `curai-default`, `curai-tools`, `curai-fast` |
| POST | `/v1/chat/completions` | JSON or SSE (`stream: true`) |

Disable with `ENABLE_OPENAI_API=false`.

## Chat / conversations

Primary app chat endpoints live under the FastAPI routes module (`app/api/routes.py`). Use the OpenAPI schema at `/docs` when the app is running for the live contract.

## Ingest

| Method | Path | Notes |
|--------|------|-------|
| POST | `/ingest` | JSON documents |
| POST | `/ingest/files` | Multipart; txt/md/pdf |

## Tools & workflows

| Method | Path |
|--------|------|
| GET | `/tools?role=chat_agent` |
| POST | `/workflow_runs` |
| GET | `/workflow_runs` |
| GET | `/workflow_runs/{run_id}` |
| POST | `/workflow_runs/{run_id}/pause` |
| POST | `/workflow_runs/{run_id}/resume` |
| POST | `/workflow_runs/{run_id}/cancel` |
| GET | `/jobs/{job_id}` |

## Admin (staff JWT)

See [Admin Portal](Admin-Portal).

## Health

| Method | Path |
|--------|------|
| GET | `/health` |
| GET | `/ready` |
| GET | `/metrics` |

## Tip

When developing, open **Swagger UI** at `/docs` — it is the source of truth for request/response schemas.
