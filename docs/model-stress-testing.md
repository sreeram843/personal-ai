# Model and API stress testing

This document records smoke and stress test methodology, results, and how to re-run against **local remote inference** (Mac Mini + LM Studio) and **production** (`https://app.cura-i.com`).

## Architecture under test

| Environment | Chat provider | Model (as of 2026-06-22) | Embeddings |
|-------------|---------------|--------------------------|------------|
| **Local remote** (`make up-remote`) | LM Studio @ `192.168.10.1:1234` | `qwen-3-14b-instruct` (Q4_K_M GGUF) | Ollama `nomic-embed-text` @ `192.168.10.1:11434` |
| **Production** | Cloud OpenAI-compatible (`.env.cloud`, e.g. Groq) | Per `LLM_CLOUD_*_MODEL` in prod env | Ollama `nomic-embed-text` on VM |

Local config lives in `.env.remote`. Production uses `docker-compose.cloud.yml` + `.env.cloud` on the GCP VM.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/real_api_smoke.sh` | Health, ready, live FX/weather (no LLM load) |
| `scripts/model_accuracy_smoke.sh` | LLM accuracy + live-data provenance |
| `scripts/model_stress_test.py` | Concurrent `POST /chat` load test |
| `scripts/verify_prod_auth.sh` | Auth/OAuth diagnostics |

### Stress test usage

```bash
# Local — default profile (8 requests, concurrency 4)
python3 scripts/model_stress_test.py --profile local \
  --output docs/results/stress-local-latest.json

# Via Docker app container (when host lacks httpx)
docker compose -f docker-compose.yml -f docker-compose.remote-inference.yml \
  --env-file .env.remote exec -T app python3 - \
  < scripts/model_stress_test.py --profile local

# Production — lighter defaults (4 requests, concurrency 2)
export BASE_URL=https://app.cura-i.com
export AUTH_TOKEN="<jwt>"   # see Authentication below
python3 scripts/model_stress_test.py --profile prod \
  --output docs/results/stress-prod-latest.json
```

Makefile shortcuts:

```bash
make model-stress-local
export AUTH_EMAIL=stress-test@example.com   # or AUTH_TOKEN=<jwt>
make model-stress-prod
```

## Authentication (production)

`/chat` requires a Bearer JWT when `AUTH_DISABLED=false` (production default).

**Option A — use an existing session token**

Copy the token from browser devtools (Application → localStorage / network `Authorization` header after Google sign-in).

**Option B — issue a test token (if `/auth/token` is enabled for email)**

```bash
curl -s -X POST https://app.cura-i.com/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"stress-test@example.com"}' | python3 -m json.tool
export AUTH_TOKEN="<access_token from response>"
```

Or set `AUTH_EMAIL=stress-test@example.com` (must be a valid RFC email — `.local` domains are rejected).

**Option C — local dev bypass**

When `AUTH_DISABLED=true`, no token is needed (local `.env.remote`).

## Metrics collected

Each stress run reports:

- **Wall latency** — client-side time including network
- **Server latency** — `latency_ms` on `ChatResponse` (end-to-end handler time)
- **Overhead** — wall − server (network + serialization)
- **Throughput** — successful requests / total batch wall time
- **Per-request log** — status, latencies, response length

Results can be saved as JSON via `--output`.

---

## Recorded results (2026-06-22)

### Local smoke test (`http://127.0.0.1:8000`)

| Check | Result |
|-------|--------|
| Docker stack | app, postgres, qdrant, redis — Up |
| `GET /health` | 200 OK |
| `GET /ready` | ready (Ollama + Qdrant OK) |
| Mac Mini reachability | `192.168.10.1:1234` OK from app container |
| `GET /auth/config` | `AUTH_DISABLED=true` |
| `POST /chat` (14B) | OK |
| `POST /chat/stream` | OK (17+25 → 42); primary UI path (`/smart_chat/stream` is a deprecated alias) |
| Sample single chat latency | **~25.2s** (`latency_ms` ≈ 25,174 ms) |

`real_api_smoke.sh`: 4/4 HTTP checks passed (provider probe skipped on host — missing `pydantic_settings` outside Docker).

### Local stress — parallel (`--profile local`: 8 req, concurrency 4)

| Metric | Value |
|--------|-------|
| Success | **8/8** |
| Total wall time | 158.0 s |
| Throughput | 0.05 req/s |
| Wall latency p50 / p95 | **76,780 ms / 110,575 ms** |
| Server latency p50 / p95 | **76,721 ms / 110,496 ms** |
| Overhead p50 | 56 ms |
| Warmup (1 req) | 10,234 ms |

Per-request wall times (ms): 80,157 · 75,757 · 115,676 · 101,101 · 68,102 · 77,803 · 46,171 · 31,749

**Interpretation:** Stable under load, but LM Studio serializes 14B requests — concurrent users see ~4× higher latency than sequential.

### Local stress — sequential (`4 req, concurrency 1, no warmup`)

| Metric | Value |
|--------|-------|
| Success | **4/4** |
| Total wall time | 87.5 s |
| Wall latency p50 / p95 | **17,505 ms / 35,782 ms** |
| Server latency p50 / p95 | **17,483 ms / 35,762 ms** |
| Overhead p50 | 21 ms |

Per-request wall times (ms): 19,626 · 15,385 · 38,634 · 13,884

**Interpretation:** Single-user interactive latency ~14–20 s for short prompts on Qwen3-14B over Ethernet.

### Production stress (`https://app.cura-i.com`, 2026-06-22)

Auth via `POST /auth/token` with `stress-test@example.com`.

| Run | Requests | Concurrency | Success | Wall p50 | Notes |
|-----|----------|-------------|---------|----------|-------|
| Parallel | 4 | 2 | **2/4** | ~2.6 s | 2× HTTP 500 under parallel load |
| Sequential | 2 | 1 | **2/2** | ~2.4 s | Stable |
| Warmup (parallel run) | 1 | — | OK | 2.56 s | |

JSON artifacts:

- `docs/results/stress-prod-parallel-2026-06-22.json`
- `docs/results/stress-prod-sequential-2026-06-22.json`
- `docs/results/stress-prod-latest.json` (index)

**Interpretation:** Production is **much faster** than local 14B (~2.5 s vs ~17 s) because prod uses cloud inference (Groq/etc.). Parallel requests at concurrency 2 caused **500 errors** on half the batch — likely rate limits or agent-path failures; use **`--concurrency 1`** for prod smoke until investigated. `latency_ms` is not yet returned on prod (deploy pending).

### Local stress JSON artifacts

- `docs/results/stress-local-parallel-2026-06-22.json`
- `docs/results/stress-local-sequential-2026-06-22.json`

---

## Recommendations

| Goal | Setting |
|------|---------|
| Best single-user latency (local) | Concurrency **1**, only **14B** loaded in LM Studio |
| Stability validation | `--profile local` (8×4) — expect 0 failures, high p50 |
| Prod validation | `--profile prod` with valid `AUTH_TOKEN`, off-peak |
| Avoid queueing | Do not run parallel stress while actively using the app |

## Related docs

- [README.md](./README.md) — documentation index
- [testing-accuracy.md](./testing-accuracy.md) — accuracy smoke, routing evals
- [compose-profiles.md](./compose-profiles.md) — local vs cloud vs remote inference
- [ops-runbook.md](./runbooks/ops-runbook.md) — deploy and prod troubleshooting
- [../frontend/CAPACITOR.md](../frontend/CAPACITOR.md) — mobile UI and simulator
- [results/README.md](./results/README.md) — JSON artifact index
