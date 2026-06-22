# Compose profiles

Personal AI uses [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/) to switch LLM runtime modes without changing application code.

## Profiles

| Profile | Chat inference | Embeddings | Make target |
|---------|----------------|------------|-------------|
| `local` | Ollama (`llama3:8b`, etc.) | Ollama (`nomic-embed-text`) | `make up` |
| `cloud-chat` | Cloud OpenAI-compatible API | Ollama (`nomic-embed-text`) | `make up-cloud` |
| `gpu-vllm` | Local vLLM on NVIDIA GPU | Ollama (`nomic-embed-text`) | `make up-gpu-vllm` |
| `remote` | LM Studio on another host (OpenAI API) | Remote Ollama (`nomic-embed-text`) | `make up-remote` |
| `workers` | (uses app LLM config) | (uses app embed config) | `make up-workers` |

Core services (Postgres, Redis, Qdrant, app, Prometheus, Grafana) always start. LLM runtime containers are profile-gated.

## Quick start

### Local (default)

```bash
make up
make pull-models   # llama3:8b + nomic-embed-text
```

Equivalent:

```bash
docker compose --profile local up -d
```

### Cloud chat

```bash
cp .env.cloud.example .env.cloud
# Edit .env.cloud — enable one provider block
make up-cloud
```

Chat routes to your cloud provider. Ollama still runs in-container for embeddings only.

`make up-cloud` also runs `make pull-models-cloud` so RAG/embeddings work on first boot.

### Production VM

GitHub Actions and manual SSH deploys use `scripts/deploy_prod.sh` (`make deploy-prod`):

1. `compose up --build` with `cloud-chat` + `workers`
2. Wait for Ollama, pull `nomic-embed-text`
3. Smoke-test `/api/embed`
4. `alembic upgrade head`, `/health`, `/ready`

On the server: `cd /opt/personal-ai && ./scripts/deploy_prod.sh`


```bash
cp .env.gpu-vllm.example .env.gpu-vllm
# Set HF_TOKEN and model ids
make up-gpu-vllm
```

Requires NVIDIA GPU + [Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html). vLLM listens on host port `8001`.

### Remote inference (Mac Mini / LM Studio)

App on one machine, chat + embeddings on another (e.g. MacBook runs Docker, Mac Mini at `192.168.1.138` runs LM Studio + Ollama):

```bash
cp .env.remote.example .env.remote
# Set LLM_*_MODEL to the id from: curl http://192.168.1.138:1234/v1/models
make up-remote
make db-migrate   # first run
```

Mac Mini must expose LM Studio on port **1234** (local network) and Ollama on **11434** (`OLLAMA_HOST=0.0.0.0:11434`).

### Background workers

Workers reuse the active LLM profile. Combine profiles:

```bash
docker compose --profile local --profile workers up -d
# or
make up-workers   # local + workers
```

## Verify active mode

```bash
docker compose exec app env | grep -E "LLM_DEFAULT_PROVIDER|LLM_OPENAI_BASE_URL|OLLAMA_BASE_URL"
```

| Mode | `LLM_DEFAULT_PROVIDER` | `LLM_OPENAI_BASE_URL` |
|------|--------------------------|------------------------|
| local | `ollama` (or unset) | empty |
| cloud-chat | `openai` | `https://api.*` |
| gpu-vllm | `openai` | `http://vllm:8000/v1` |

`OLLAMA_BASE_URL=http://ollama:11434` should be set in all modes for embeddings.

## Validate compose files

```bash
make compose-validate
```

## Related files

- `docker-compose.yml` — base stack + profile definitions
- `docker-compose.cloud.yml` — cloud-chat env overrides
- `docker-compose.gpu-vllm.yml` — gpu-vllm env overrides
- `docker-compose.remote-inference.yml` — LM Studio + remote Ollama (no local Ollama container)
- `docker-compose.dmr.yml` — macOS Docker Model Runner (separate from profiles)
- `.env.cloud.example` / `.env.gpu-vllm.example` / `.env.remote.example` — profile env templates
