# Testing and accuracy evaluation

This project uses layered tests to verify correctness, tenant isolation, and routing accuracy without relying on live LLM calls in CI.

## Layers

| Layer | What it checks | Examples |
|-------|----------------|----------|
| Unit | Pure functions and store semantics | `test_object_storage.py`, `test_workflow_memory_scoping.py` |
| API integration | Auth, persistence, HTTP contracts | `test_workflow_run_routes.py`, `test_ingest_scoping.py` |
| Golden-set eval | Expected routing decisions on fixed queries | `tests/fixtures/routing_golden.json` + `test_eval_routing_accuracy.py` |
| Property-style isolation | Cross-product of users × conversation IDs | `test_eval_tenant_isolation.py` |
| Grounding guards | Citation metadata and response cleanup | `test_eval_rag_grounding.py` |
| Background workers | Async ingest enqueue + inline worker execution | `test_background_workers.py` |

## Routing golden set

`tests/fixtures/routing_golden.json` holds labeled queries. Each case asserts:

- `_select_smart_mode` → `chat` | `rag` | `workflow`
- `should_run_web_research` and `should_route_smart_toward_workflow` flags

Add new cases when you change heuristics in `information_routing.py` or `_select_smart_mode`.

## Tenant isolation

Run stores and workflow memory use per-user namespaces. Property tests vary:

- User ID pairs (including UUID-shaped IDs)
- Shared conversation IDs across tenants

A leak would surface as foreign summaries or runs visible to the wrong `user_id`.

## RAG grounding

`test_eval_rag_grounding.py` does not call an LLM. It verifies:

- Source metadata survives the response model (path, score)
- `_format_chat_response` strips legacy prefixes that would confuse citation parsing

For deeper RAG evals, add fixture chunks and assert the orchestrator includes `[[evidence:<id>]]` markers when evidence is injected (mock gateway).

## Optional extensions (not required in CI)

- **LLM-as-judge**: score answers against a rubric; keep behind a manual `pytest -m eval` marker
- **Snapshot tests**: freeze routing decisions when refactoring heuristics
- **Playwright flows**: upload → job poll → chat with citations (`frontend/tests/ui-flows.spec.ts`)

## Running eval-focused tests

```bash
python -m pytest tests/test_eval_routing_accuracy.py tests/test_eval_rag_grounding.py tests/test_eval_tenant_isolation.py -v
```

## Real API integration (live providers)

Hit Frankfurter, Open-Meteo, and Yahoo Finance — no mocks:

```bash
make test-real-api
# or
RUN_REAL_API_TESTS=1 pytest tests/test_real_api_integration.py -v --no-cov
```

Includes a full HTTP test via `TestClient` (real Postgres + live FX). For a server already on `:8000`:

```bash
make db-migrate
uvicorn app.main:app --reload   # restart after code changes
make real-api-smoke
```

### Model + live-data accuracy (running stack)

Compare chat answers and verified live feeds against ground truth (Frankfurter, Open-Meteo, Yahoo, plus LLM math/fact probes):

```bash
make model-accuracy-smoke
# or
bash scripts/model_accuracy_smoke.sh
```

Checks: live FX/weather/stock provenance, basic math, factual recall. Requires the app on `:8000` with inference reachable (e.g. `make up-remote`).

### Model stress testing (load + latency)

Concurrent `POST /chat` against local remote inference or production. Full recorded data:

- **[model-stress-testing.md](./model-stress-testing.md)** — methodology + all results
- **[results/README.md](./results/README.md)** — JSON artifacts

```bash
make model-stress-local
export AUTH_EMAIL=stress-test@example.com
make model-stress-prod
```

**Summary (2026-06-22):** Local Qwen3-14B sequential p50 **17.5 s**; parallel (c4) p50 **76.8 s** (stable, queued). Production sequential p50 **2.4 s**; parallel c2 had 2/4 HTTP 500 — use concurrency 1 on prod.

Prerequisites: Postgres with `personal_ai` DB. Qdrant/Ollama only needed for RAG/LLM chat — live FX/weather short-circuit works without them after lazy vector-store init.
