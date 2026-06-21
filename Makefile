.PHONY: help build up up-local up-cloud up-gpu-vllm up-remote up-workers up-dmr down logs logs-app logs-worker logs-ollama logs-qdrant restart clean pull-models status test-backend test-frontend test-real-api test-real-api-http real-api-smoke model-accuracy-smoke security-check compose-validate compose-smoke quality-gate shell-app penpot-mcp db-migrate db-revision

COMPOSE_PROFILES_BASE=--profile local --profile cloud-chat --profile gpu-vllm --profile workers

help:
	@echo "Personal AI Docker Compose Commands"
	@echo "===================================="
	@echo "make build          - Build all images"
	@echo "make up             - Start stack (profile: local — Ollama chat + embeds)"
	@echo "make up-cloud       - Start stack (profile: cloud-chat — cloud chat, local embeds)"
	@echo "make up-gpu-vllm    - Start stack (profile: gpu-vllm — vLLM chat, local embeds)"
	@echo "make up-remote      - Start stack (LM Studio + Ollama on Mac Mini, no local Ollama)"
	@echo "make up-workers     - Start local stack + ARQ background worker"
	@echo "make up-dmr         - Start with Docker Model Runner (macOS only)"
	@echo "make down           - Stop all services"
	@echo "make restart        - Restart all services"
	@echo "make logs           - View all logs"
	@echo "make logs-app       - View app logs"
	@echo "make logs-worker    - View background worker logs"
	@echo "make logs-ollama    - View ollama logs"
	@echo "make logs-qdrant    - View qdrant logs"
	@echo "make clean          - Remove containers and volumes"
	@echo "make pull-models    - Pull Ollama models (llama3:8b, nomic-embed-text)"
	@echo "make status         - Show container status"
	@echo "make test-real-api  - Hit live FX/weather/stock providers (no mocks)"
	@echo "make real-api-smoke - Provider + HTTP smoke (needs app on :8000)"
	@echo "make model-accuracy-smoke - LLM + live-data accuracy checks (needs app on :8000)"
	@echo "make test-frontend  - Run Playwright browser suite"
	@echo "make security-check - Run lightweight security checks"
	@echo "make compose-validate - Validate docker compose config"
	@echo "make compose-smoke - Run lightweight docker compose smoke test"
	@echo "make quality-gate   - Run the unified repo quality gate"
	@echo "make penpot-mcp     - Start local Penpot MCP server (see docs/penpot-mcp.md)"
	@echo "make db-migrate     - Apply Alembic migrations (requires Postgres)"
	@echo "make db-revision    - Create a new Alembic revision (autogenerate)"

build:
	docker compose build

up:
	docker compose --profile local up -d
	@echo ""
	@echo "Services started (profile: local)"
	@echo "  App:        http://localhost:8000"
	@echo "  Ollama:     http://localhost:11434"
	@echo "  Qdrant:     http://localhost:6333"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3000"
	@echo "  Loki:       http://localhost:3100 (logs via Grafana)"

up-local: up

up-dmr:
	docker compose --profile local -f docker-compose.yml -f docker-compose.dmr.yml up -d

up-cloud:
	@if [ ! -f .env.cloud ]; then \
		echo "ERROR: .env.cloud not found. Copy .env.cloud.example and fill in your API key."; \
		exit 1; \
	fi
	docker compose --profile cloud-chat -f docker-compose.yml -f docker-compose.cloud.yml --env-file .env.cloud up -d
	@echo ""
	@echo "Services started (profile: cloud-chat)"
	@echo "  App:        http://localhost:8000"
	@echo "  Ollama:     http://localhost:11434 (embeddings only)"
	@echo "  Qdrant:     http://localhost:6333"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3000"
	@echo "  Loki:       http://localhost:3100 (logs via Grafana)"

up-gpu-vllm:
	@if [ ! -f .env.gpu-vllm ]; then \
		echo "ERROR: .env.gpu-vllm not found. Copy .env.gpu-vllm.example and set HF_TOKEN."; \
		exit 1; \
	fi
	docker compose --profile gpu-vllm -f docker-compose.yml -f docker-compose.gpu-vllm.yml --env-file .env.gpu-vllm up -d
	@echo ""
	@echo "Services started (profile: gpu-vllm)"
	@echo "  App:        http://localhost:8000"
	@echo "  vLLM:       http://localhost:8001/v1"
	@echo "  Ollama:     http://localhost:11434 (embeddings only)"
	@echo "  Qdrant:     http://localhost:6333"

up-remote:
	@if [ ! -f .env.remote ]; then \
		echo "ERROR: .env.remote not found. Run: cp .env.remote.example .env.remote"; \
		echo "       Then set LLM_*_MODEL to your LM Studio model id."; \
		exit 1; \
	fi
	docker compose -f docker-compose.yml -f docker-compose.remote-inference.yml --env-file .env.remote up -d --build
	@REMOTE_HOST=$$(grep -E '^OLLAMA_BASE_URL=' .env.remote | sed -E 's|^[^/]*//||; s|:.*||'); \
	echo ""; \
	echo "Services started (remote inference @ $$REMOTE_HOST)"; \
	echo "  App:        http://localhost:8000"; \
	echo "  LM Studio:  http://$$REMOTE_HOST:1234 (chat)"; \
	echo "  Ollama:     http://$$REMOTE_HOST:11434 (embeddings)"; \
	echo "  Qdrant:     http://localhost:6333"; \
	echo ""; \
	echo "Verify Mac Mini: curl http://$$REMOTE_HOST:1234/v1/models"; \
	echo "                 curl http://$$REMOTE_HOST:11434/api/tags"

up-workers:
	docker compose --profile local --profile workers up -d
	@echo ""
	@echo "Services started (profiles: local + workers)"

down:
	docker compose $(COMPOSE_PROFILES_BASE) down --remove-orphans

restart: down up

logs:
	docker compose logs -f

logs-app:
	docker compose logs -f app

logs-worker:
	docker compose --profile workers logs -f worker

logs-ollama:
	docker compose logs -f ollama

logs-qdrant:
	docker compose logs -f qdrant

clean:
	docker compose down -v
	@echo "✅ Containers and volumes removed"

pull-models:
	docker compose --profile local exec ollama ollama pull llama3:8b
	docker compose --profile local exec ollama ollama pull nomic-embed-text
	@echo "✅ Models pulled successfully"

status:
	docker compose ps

test-backend:
	python -m pytest

test-frontend:
	cd frontend && npm run test:ui

test-real-api:
	RUN_REAL_API_TESTS=1 python -m pytest tests/test_real_api_integration.py -v --no-cov -k "not http"

test-real-api-http:
	RUN_REAL_API_TESTS=1 RUN_HTTP_API_TESTS=1 python -m pytest tests/test_real_api_integration.py -v --no-cov

real-api-smoke:
	bash scripts/real_api_smoke.sh

model-accuracy-smoke:
	bash scripts/model_accuracy_smoke.sh

security-check:
	python scripts/security_checks.py

compose-validate:
	docker compose --profile local config >/dev/null
	docker compose --profile cloud-chat -f docker-compose.yml -f docker-compose.cloud.yml config >/dev/null
	docker compose --profile gpu-vllm -f docker-compose.yml -f docker-compose.gpu-vllm.yml config >/dev/null
	docker compose --env-file .env.remote.example -f docker-compose.yml -f docker-compose.remote-inference.yml config >/dev/null
	docker compose --profile local --profile workers config >/dev/null
	@echo "docker compose profiles validated (local, cloud-chat, gpu-vllm, remote, workers)"

compose-smoke:
	bash scripts/compose_smoke.sh

quality-gate:
	./scripts/quality_gate.sh

shell-app:
	docker compose exec app /bin/bash

penpot-mcp:
	npx -y @penpot/mcp@stable

db-migrate:
	alembic upgrade head

db-revision:
	alembic revision --autogenerate -m "$(MSG)"
