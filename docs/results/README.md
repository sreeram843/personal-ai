# Benchmark & smoke test results

Machine-readable artifacts and summary tables from recorded runs (**2026-06-22**).

Full methodology and interpretation: [../model-stress-testing.md](../model-stress-testing.md).

## Artifact index

| File | Environment | Type | Key outcome |
|------|-------------|------|-------------|
| [smoke-local-2026-06-22.json](./smoke-local-2026-06-22.json) | Local `:8000` | Smoke | Health, ready, chat, smart stream OK |
| [smoke-prod-2026-06-22.json](./smoke-prod-2026-06-22.json) | `app.cura-i.com` | Smoke | Sequential OK; parallel c2 had 2× HTTP 500 |
| [stress-local-parallel-2026-06-22.json](./stress-local-parallel-2026-06-22.json) | Local remote 14B | Stress 8×c4 | **8/8** pass, p50 **76.8 s** |
| [stress-local-sequential-2026-06-22.json](./stress-local-sequential-2026-06-22.json) | Local remote 14B | Stress 4×c1 | **4/4** pass, p50 **17.5 s** |
| [stress-prod-parallel-2026-06-22.json](./stress-prod-parallel-2026-06-22.json) | `app.cura-i.com` | Stress 4×c2 | **2/4** pass, 2× HTTP 500 |
| [stress-prod-sequential-2026-06-22.json](./stress-prod-sequential-2026-06-22.json) | `app.cura-i.com` | Stress 2×c1 | **2/2** pass, p50 **2.4 s** |
| [stress-prod-latest.json](./stress-prod-latest.json) | Production | Index | Points to prod artifacts |
| [eggplant-latest.json](./eggplant-latest.json) | Offline | Dataset eval | External benchmark download + probe summary |

## Eggplant dataset eval

Methodology and interpretation: [../eggplant-eval.md](../eggplant-eval.md).

```bash
make eggplant-setup
make eggplant-download
make eggplant-eval
```

## Summary comparison

| Metric | Local 14B (sequential) | Local 14B (parallel c4) | Production (sequential) |
|--------|------------------------|-------------------------|-------------------------|
| Success rate | 4/4 (100%) | 8/8 (100%) | 2/2 (100%) |
| Latency p50 | **17.5 s** | **76.8 s** | **2.4 s** |
| Latency p95 | 35.8 s | 110.6 s | 2.5 s |
| Throughput | ~0.05 req/s | ~0.05 req/s | ~0.42 req/s |
| Inference | Mac Mini LM Studio | Mac Mini (queued) | Cloud API |

## Local smoke (2026-06-22)

| Check | Result |
|-------|--------|
| Docker stack | app, postgres, qdrant, redis — Up |
| `GET /health` | 200 |
| `GET /ready` | ready (Ollama + Qdrant) |
| Mac Mini `192.168.10.1:1234` | Reachable from app container |
| `POST /chat` (14B) | OK, ~25 s sample |
| `POST /chat/stream` | OK (primary UI path; `/smart_chat/stream` is a deprecated alias) |
| `real_api_smoke.sh` | 4/4 HTTP checks |

## Production smoke (2026-06-22)

| Check | Result |
|-------|--------|
| `GET /health` | 200 |
| `GET /ready` | ready |
| Auth | `POST /auth/token` with `stress-test@example.com` |
| Sequential chat | 2/2 OK, ~2.2–2.5 s |
| Parallel chat (c2) | 2/4 OK, 2× HTTP 500 |
| `latency_ms` in response | Not deployed on prod yet |

## Re-run and append results

```bash
# Local stress → save JSON (from repo root, via Docker)
make model-stress-local

# Production (sequential recommended)
export AUTH_EMAIL=stress-test@example.com
make model-stress-prod
```

Name new files `stress-{env}-{scenario}-YYYY-MM-DD.json` and add a row to the index table above.
