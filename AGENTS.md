# AGENTS.md

## Knowledge graph MCP (use first)

This repo has a `code-review-graph` MCP server (registered in `.opencode.json`). The
graph auto-updates on file changes and gives structural context (callers, dependents,
test coverage) that file scanning cannot. Use these **before** Grep/Glob/Read:

- Exploration: `semantic_search_nodes` / `query_graph`
- Impact: `get_impact_radius` / `get_affected_flows`
- Review: `detect_changes` + `get_review_context`
- Coverage: `query_graph` pattern="tests_for"

Fall back to file tools only when the graph lacks the coverage you need.

## What this is

Monorepo: FastAPI + Postgres + Qdrant + Redis backend (`app/`), React 19 + Vite 7
frontend (`frontend/`). Multi-user RAG assistant ("CurieAI"). Chat auto-routes each
message: live-data short-circuit → `chat` / `rag` / `workflow`.

## Commands

- Full gate (CI runs this): `./scripts/quality_gate.sh` (`make quality-gate`) —
  compose validate, security checks, `compileall`, backend pytest (cov≥35%),
  frontend lint+build+unit, Playwright (linux), Docker build, compose smoke.
- Backend tests: `./.venv/bin/python3 -m pytest` (use the repo venv, not system python)
  - one test: `./.venv/bin/python3 -m pytest tests/test_auth.py::test_foo`
- Frontend (from `frontend/`): `npm run lint`, `npm run build`, `npm run test:unit`
  (Vitest), `npm run test:ui` (Playwright), `npm run test:e2e`, `npm run test:visual`
- Migrations: `alembic upgrade head` (`make db-migrate`); new revision
  `make db-revision MSG="..."` (autogenerate).
- Live/real API tests are opt-in: `RUN_REAL_API_TESTS=1` and `RUN_HTTP_API_TESTS=1`
  (skipped by default; see `make test-real-api`).
- Eval suite: `make test-eval` (runs the `test_eval_*` golden modules, `--no-cov`).

## Layout

- `app/main.py` — `create_app()`; singleton `app` + all routers.
- `app/api/` routes · `app/services/` business logic (largest area: chat, tools, live
  data) · `app/core/` config/auth/deps · `app/schemas/` Pydantic · `app/db/` SQLAlchemy
  + Alembic.
- `app/prompts/system.md` — assistant persona (governed by `docs/traits.md`).
- `tests/` mirrors `app/`; uses in-memory SQLite + FastAPI dependency overrides
  (`tests/conftest.py`) — no external services needed.
- `memory/` — file-backed runtime state (`user_skills.json`, `uploads/`, `runs/`). Tests
  isolate it via tmp_path env overrides; don't touch it directly.

## Gotchas

- Multiple env files per runtime profile: `.env` (local/Ollama), `.env.cloud`,
  `.env.remote`, `.env.gpu-vllm`. Compose profiles: `local` (default), `cloud-chat`,
  `gpu-vllm`, `remote`, `workers`. `make up` is local only.
- `get_settings()` is cached; after changing env/settings (esp. in tests) call
  `get_settings.cache_clear()`.
- Playwright visual baselines: CI is Linux — commit both `*-darwin.png` and
  `*-linux.png`; regenerate Linux with `npm run test:visual:update:linux`.
- Coverage gate is `--cov-fail-under=35`; don't lower it casually.
- Chat execution strategies are selected by `ENABLE_FAST_CHAT` / `ENABLE_TOOL_AGENT`:
  `fast_chat.py`, `tool_agent.py`, `orchestrated_chat.py`.

## Conventions

- Python: type hints, snake_case, PEP 8; request/response models in `app/schemas/`;
  new deps must be pinned in `requirements.txt`.
- Frontend: strict TypeScript (no `any`), shared types in `frontend/src/types.ts`,
  Tailwind (no inline styles / hardcoded colors — use CSS vars from `index.css`).
- `app/core/config.py` + env vars for all config; no hardcoded values.

## Documentation

Single source of truth; link, don't duplicate. Doc map:

- `README.md` — landing + routing table (users). `CONTRIBUTING.md` — human workflow.
- `docs/architecture.md` — system design + the "why" (read before "fixing" a tradeoff).
- `docs/adr/` — architecture decision records; numbers never reused, superseded not deleted.
- `docs/api.md` — API surface. `docs/traits.md` — assistant governance.
- `docs/runbooks/` — operations/deploy playbooks (symptom → diagnosis → action).

Doc updates ship **in the same PR** as the behavior change, never as a follow-up.
Significant new decisions get a new numbered ADR.
