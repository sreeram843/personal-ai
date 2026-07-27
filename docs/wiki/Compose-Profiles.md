# Compose Profiles

Compose files stack: `docker-compose.yml` + overlays (`docker-compose.cloud.yml`, GPU, etc.).

## Common profiles

| Profile / stack | Use |
|-----------------|-----|
| Default `docker compose up` | Local full stack (API, Ollama, Qdrant, Redis, …) |
| `cloud-chat` | Production-shaped chat: Postgres, cloud LLM wiring, Caddy-friendly |
| `workers` | Background ingest / workflow workers (ARQ) |
| Observability | Prometheus, Grafana, Loki (see ops runbook ports) |
| GPU / vLLM | See `.env.gpu-vllm.example` and GPU compose docs |

## Production-style local / VM

```bash
docker compose --profile cloud-chat --profile workers \
  -f docker-compose.yml -f docker-compose.cloud.yml \
  --env-file .env.cloud up --build
```

Prefer wrappers:

```bash
./scripts/deploy_prod.sh
# or
make deploy-prod
```

## Local ports (typical)

| Service | Port |
|---------|------|
| App | 8000 |
| Ollama | 11434 |
| Qdrant | 6333 |
| Redis | 6379 |
| Prometheus | 9090 |
| Grafana | 3000 |
| Loki | 3100 |

## Related

- [Getting Started](Getting-Started)
- [Deployment](Deployment)
- [Operations](Operations)
- In-repo: `docs/compose-profiles.md` (if present), `docs/ops-runbook.md`
