# API reference

CurieAI exposes a JSON HTTP API plus a subset of the OpenAI Chat Completions API.
Auth is JWT (`Authorization: Bearer <token>`) when `AUTH_DISABLED=false`; local dev
defaults to `AUTH_DISABLED=true` with a dev user injected automatically.

To obtain a token when auth is enabled:

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}'
```

Conversation and message APIs are scoped per user. RAG ingest and search filter
Qdrant by `user_id`.

## Auth

| Endpoint | Description |
|----------|-------------|
| `GET /auth/config` | Public login config (Google client id, legal URLs, `support_email`) |
| `POST /auth/google` | Exchange a Google ID token for a JWT |
| `POST /auth/logout` | Audit `auth.sign_out` (JWT remains stateless; client drops the token) |
| `GET /auth/me` | Current user |
| `GET /auth/me/export` | Account data export |
| `DELETE /auth/me` | Delete account |

Support contact defaults to `hello@cura-i.com` (`SUPPORT_EMAIL`). Public legal pages: `/privacy`, `/terms`. Domain split: [marketing-site.md](./marketing-site.md).

## Chat

| Endpoint | Description |
|----------|-------------|
| `POST /chat` | Direct chat (fast path; no smart auto-routing) |
| `POST /chat/stream` | SSE stream for direct chat |
| `POST /smart_chat` | Smart chat with auto-routing (live data, chat / rag / workflow) |
| `POST /smart_chat/stream` | SSE stream for smart chat |
| `POST /rag_chat` | RAG-grounded chat with citations |
| `POST /workflow_chat` | Explicit workflow with trace |
| `POST /workflow_chat/stream` | SSE workflow stream |
| `POST /workflow_chat/background` | Enqueue long workflow to worker |
| `POST /ingest` | Upload documents (`multipart/form-data`, field `files`) |

Request body (chat): `{ "messages": [{"role":"user","content":"..."}], "conversation_id": "<uuid>" }`.
Shorthand: `{ "message": "..." }` is also accepted.

Chat responses include optional `latency_ms` (end-to-end handler time), persisted on
assistant messages in Postgres metadata for history reload.

## Conversations

| Endpoint | Description |
|----------|-------------|
| `GET /conversations` | List conversations for current user |
| `POST /conversations` | Create conversation |
| `GET /conversations/{id}/messages` | Message history |
| `DELETE /conversations/{id}` | Delete conversation |

Create with an optional `assistant_id` to bind a skill/assistant for the whole
thread. Use `"default"` or omit for the general CurieAI assistant.

## Assistants & agent settings

| Endpoint | Description |
|----------|-------------|
| `GET /agent/assistants` | List assistants (includes synthetic `default`) |
| `POST /agent/assistants` | Create a pick-only custom assistant |
| `PATCH /agent/assistants/{id}` | Update or enable/disable bundled assistants |
| `DELETE /agent/assistants/{id}` | Delete a custom assistant |

In the UI, pick an assistant from the sidebar before starting a conversation, or
manage them under **Agent settings → Assistants**.

When a message matches more than one skill trigger, CurieAI prefers the skill
this user has used most often (implicit counts in `memory/skill_implicit.json`,
separate from explicit enable/disable `_pref_` records). An explicit assistant
pick (`assistant_id`) does not update those counts. Disabled bundled skills are
never selected. On a count tie or with no history, bundled first-match order
is kept.

## OpenAI-compatible API (`/v1`)

Same JWT auth as the web app. Set `ENABLE_OPENAI_API=false` to disable.

| Endpoint | Description |
|----------|-------------|
| `GET /v1/models` | Lists `curai-default`, `curai-tools`, `curai-fast` |
| `POST /v1/chat/completions` | Chat completion (JSON or SSE when `stream: true`) |

Models map to execution strategies: `curai-tools` forces the tool agent;
`curai-fast` forces fast chat; `curai-default` uses normal routing. Pass
`metadata.assistant_id` or top-level `assistant_id` to bind a skill for that request.

```bash
curl -s http://localhost:8000/v1/models | python3 -m json.tool

curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"curai-default","messages":[{"role":"user","content":"hello"}]}' \
  | python3 -m json.tool
```

Point any OpenAI SDK at your CurieAI host via `base_url`, supplying a bearer token when
auth is enabled.

## Runtime MCP

Per-user HTTP MCP connectors (design and security:
[mcp-runtime.md](./mcp-runtime.md)). Gated by `ENABLE_RUNTIME_MCP`.

| Endpoint | Description |
|----------|-------------|
| `GET /mcp/servers` | List current user's connectors (`header_keys` only) |
| `POST /mcp/servers` | Register HTTP MCP URL + optional headers |
| `PATCH /mcp/servers/{server_id}` | Update name, url, enabled, or headers |
| `DELETE /mcp/servers/{server_id}` | Remove connector |
| `POST /mcp/servers/{server_id}/test` | `tools/list` (up to 40 names) |

## Tools, workflow runs, jobs

| Endpoint | Description |
|----------|-------------|
| `GET /tools?role=chat_agent` | Tools available to the chat agent |
| `POST /workflow_runs` | Create workflow run record |
| `GET /workflow_runs` | List runs (by `conversation_id`) |
| `GET /workflow_runs/{run_id}` | Fetch run |
| `POST /workflow_runs/{run_id}/pause` | Pause run |
| `POST /workflow_runs/{run_id}/resume` | Resume run |
| `POST /workflow_runs/{run_id}/cancel` | Cancel run |
| `GET /jobs/{job_id}` | Background job status (ingest / workflow) |

Built-in tools (registered in `ToolRegistry`): `fx_rate`, `market_price`, `weather`,
`weather_forecast`, `news`, `web_search`, `find_nearby_places`.

## Health & observability

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `GET /ready` | Readiness (Qdrant + Ollama) |
| `GET /metrics` | Prometheus scrape |
