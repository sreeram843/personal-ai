.PHONY: help build build-cloud up up-local up-cloud up-gpu-vllm up-remote up-workers up-dmr down logs logs-app logs-worker logs-ollama logs-qdrant restart clean pull-models pull-models-cloud deploy-prod status test-backend test-frontend test-real-api test-real-api-http real-api-smoke model-accuracy-smoke model-stress-local model-stress-prod prod-deep-smoke security-check compose-validate compose-smoke quality-gate shell-app penpot-mcp db-migrate db-revision eggplant-setup eggplant-download eggplant-eval eggplant-eval-live eggplant-eval-live-full test-eval check-remote-inference

COMPOSE_PROFILES_BASE=--profile local --profile cloud-chat --profile gpu-vllm --profile workers
COMPOSE_CLOUD=docker compose --profile cloud-chat --profile workers -f docker-compose.yml -f docker-compose.cloud.yml --env-file .env.cloud

help:
	@echo "Personal AI Docker Compose Commands"
	@echo "===================================="
	@echo "make build          - Build all images (all compose profiles)"
	@echo "make build-cloud    - Build cloud-chat stack images (.env.cloud)"
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
	@echo "make pull-models    - Pull Ollama chat + embed models (local profile)"
	@echo "make pull-models-cloud - Pull nomic-embed-text only (cloud-chat / prod)"
	@echo "make deploy-prod    - Full production deploy (cloud-chat + workers + embed pull)"
	@echo "make status         - Show container status"
	@echo "make test-real-api  - Hit live FX/weather/stock providers (no mocks)"
	@echo "make real-api-smoke - Provider + HTTP smoke (needs app on :8000)"
	@echo "make model-accuracy-smoke - LLM + live-data accuracy checks (needs app on :8000)"
	@echo "make model-stress-local   - Concurrent chat stress test (local remote inference)"
	@echo "make model-stress-prod    - Lighter chat stress test (needs AUTH_TOKEN, app.cura-i.com)"
	@echo "make prod-deep-smoke      - Deep prod smoke (needs AUTH_TOKEN JWT from browser)"
	@echo "make test-frontend  - Run Playwright browser suite"
	@echo "make security-check - Run lightweight security checks"
	@echo "make compose-validate - Validate docker compose config"
	@echo "make compose-smoke - Run lightweight docker compose smoke test"
	@echo "make quality-gate   - Run the unified repo quality gate"
	@echo "make penpot-mcp     - Start local Penpot MCP server (see docs/penpot-mcp.md)"
	@echo "make db-migrate     - Apply Alembic migrations (requires Postgres)"
	@echo "make db-revision    - Create a new Alembic revision (autogenerate)"
	@echo "make eggplant-setup    - Create isolated eggplant venv for dataset eval"
	@echo "make eggplant-download - Download HF datasets from eggplant/manifest.json"
	@echo "make eggplant-eval     - Run offline dataset verification + write docs"
	@echo "make eggplant-eval-live - Offline eval + live /chat smoke (LM Studio via up-remote)"
	@echo "make eggplant-eval-live-full - Live chat + indirect RAG injection + workflow + connectivity"
	@echo "make test-eval          - Run all test_eval_* golden pytest modules"
	@echo "make check-remote-inference - Curl LM Studio + Ollama before live tests"

build:
	docker compose $(COMPOSE_PROFILES_BASE) build

build-cloud:
	@if [ ! -f .env.cloud ]; then \
		echo "ERROR: .env.cloud not found. Copy .env.cloud.example and fill in your API key."; \
		exit 1; \
	fi
	@set -a && . ./.env.cloud && set +a && \
	 $(COMPOSE_CLOUD) build

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
	@set -a && . ./.env.cloud && set +a && \
	 docker compose --profile cloud-chat -f docker-compose.yml -f docker-compose.cloud.yml --env-file .env.cloud up -d
	@$(MAKE) pull-models-cloud
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
	echo "Verify Mac Mini: curl http://$$REMOTE_HOST:1234/api/v1/models"; \
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
	docker logs -f personal-ai-app

logs-worker:
	$(COMPOSE_CLOUD) logs -f worker

logs-ollama:
	docker logs -f personal-ai-ollama

logs-qdrant:
	docker logs -f personal-ai-qdrant

clean:
	docker compose down -v
	@echo "✅ Containers and volumes removed"

pull-models:
	docker compose --profile local exec -T ollama ollama pull llama3:8b
	docker compose --profile local exec -T ollama ollama pull nomic-embed-text
	@echo "✅ Models pulled successfully"

pull-models-cloud:
	@printf 'Waiting for Ollama...\n'
	@for attempt in 1 2 3 4 5 6 7 8 9 10; do \
		curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; \
		if [ $$attempt -eq 10 ]; then echo "ERROR: Ollama not ready on :11434"; exit 1; fi; \
		sleep 2; \
	done
	docker exec personal-ai-ollama ollama pull nomic-embed-text
	@echo "✅ Embedding model ready for cloud-chat / prod"

deploy-prod:
	bash scripts/deploy_prod.sh

status:
	docker ps --filter name=personal-ai

test-backend:
	python -m pytest --cov-fail-under=35

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

model-stress-local:
	docker compose -f docker-compose.yml -f docker-compose.remote-inference.yml --env-file .env.remote exec -T app python3 - \
		< scripts/model_stress_test.py --profile local \
		--output docs/results/stress-local-latest.json

model-stress-prod:
	@if [ -z "$$AUTH_TOKEN" ] && [ -z "$$AUTH_EMAIL" ]; then echo "ERROR: set AUTH_TOKEN or AUTH_EMAIL (see docs/model-stress-testing.md)"; exit 1; fi
	BASE_URL=$${BASE_URL:-https://app.cura-i.com} docker compose -f docker-compose.yml -f docker-compose.remote-inference.yml --env-file .env.remote exec -T \
		-e BASE_URL=$${BASE_URL:-https://app.cura-i.com} \
		-e AUTH_TOKEN=$${AUTH_TOKEN:-} \
		-e AUTH_EMAIL=$${AUTH_EMAIL:-} \
		app python3 - < scripts/model_stress_test.py --profile prod --concurrency 1 --requests 4 \
		--label prod-$$(date -u +%Y%m%dT%H%M%SZ) || true
	@echo "Note: JSON output inside container is not persisted; copy from stdout or run host-side with httpx."

prod-deep-smoke:
	@if [ -z "$$AUTH_TOKEN" ] && [ -z "$$PROD_SMOKE_AUTH_TOKEN" ]; then \
		echo "ERROR: set AUTH_TOKEN from browser localStorage key personal-ai-auth-token (see docs/prod-smoke.md)"; \
		exit 1; \
	fi
	APP_URL=$${APP_URL:-https://app.cura-i.com} bash scripts/prod_deep_smoke.sh

security-check:
	python scripts/security_checks.py

compose-validate:
	docker compose --profile local config >/dev/null
	docker compose --profile cloud-chat -f docker-compose.yml -f docker-compose.cloud.yml config >/dev/null
	docker compose --profile gpu-vllm -f docker-compose.yml -f docker-compose.gpu-vllm.yml config >/dev/null
	@if [ ! -f .env.remote ]; then cp .env.remote.example .env.remote; fi
	docker compose --env-file .env.remote -f docker-compose.yml -f docker-compose.remote-inference.yml config >/dev/null
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

eggplant-setup:
	bash eggplant/scripts/setup.sh

eggplant-download:
	bash eggplant/scripts/download_datasets.sh

eggplant-eval:
	bash eggplant/scripts/run_eval.sh

eggplant-eval-live:
	bash eggplant/scripts/run_eval.sh --live-llm

eggplant-eval-live-full:
	bash eggplant/scripts/run_eval.sh --live-full

test-eval:
	.venv/bin/python -m pytest tests/test_eval_routing_accuracy.py tests/test_eval_rag_grounding.py tests/test_eval_tenant_isolation.py tests/test_eval_retrieval_accuracy.py tests/test_eval_tool_routing.py tests/test_eval_workflow_routing.py -q --no-cov

check-remote-inference:
	bash scripts/check_remote_inference.sh
