.PHONY: help build up down logs logs-app logs-ollama logs-qdrant restart clean pull-models status test-backend test-frontend security-check compose-validate compose-smoke quality-gate shell-app

help:
	@echo "Personal AI Docker Compose Commands"
	@echo "===================================="
	@echo "make build          - Build all images"
	@echo "make up             - Start all services"
	@echo "make down           - Stop all services"
	@echo "make restart        - Restart all services"
	@echo "make logs           - View all logs"
	@echo "make logs-app       - View app logs"
	@echo "make logs-ollama    - View ollama logs"
	@echo "make logs-qdrant    - View qdrant logs"
	@echo "make clean          - Remove containers and volumes"
	@echo "make pull-models    - Pull Ollama models (llama3:8b, nomic-embed-text)"
	@echo "make status         - Show container status"
	@echo "make test-backend   - Run backend pytest suite"
	@echo "make test-frontend  - Run Playwright browser suite"
	@echo "make security-check - Run lightweight security checks"
	@echo "make compose-validate - Validate docker compose config"
	@echo "make compose-smoke - Run lightweight docker compose smoke test"
	@echo "make quality-gate   - Run the unified repo quality gate"

build:
	docker compose build

up:
	docker compose up -d
	@echo ""
	@echo "✅ All services started!"
	@echo ""
	@echo "Services available at:"
	@echo "  App:      http://localhost:8000"
	@echo "  Ollama:   http://localhost:11434"
	@echo "  Qdrant:   http://localhost:6333"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3000"
	@echo ""
	@echo "Run 'make logs' to see logs"

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

logs-app:
	docker compose logs -f app

logs-ollama:
	docker compose logs -f ollama

logs-qdrant:
	docker compose logs -f qdrant

clean:
	docker compose down -v
	@echo "✅ Containers and volumes removed"

pull-models:
	docker compose exec ollama ollama pull llama3:8b
	docker compose exec ollama ollama pull nomic-embed-text
	@echo "✅ Models pulled successfully"

status:
	docker compose ps

test-backend:
	python -m pytest

test-frontend:
	cd frontend && npm run test:ui

security-check:
	python scripts/security_checks.py

compose-validate:
	docker compose config > /dev/null
	@echo "docker-compose.yml is valid"

compose-smoke:
	bash scripts/compose_smoke.sh

quality-gate:
	./scripts/quality_gate.sh

shell-app:
	docker compose exec app /bin/bash
