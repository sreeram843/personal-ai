.PHONY: help build up down logs logs-backend logs-frontend logs-ollama logs-qdrant restart clean pull-models

help:
	@echo "Personal AI Docker Compose Commands"
	@echo "===================================="
	@echo "make build          - Build all images"
	@echo "make up             - Start all services"
	@echo "make down           - Stop all services"
	@echo "make restart        - Restart all services"
	@echo "make logs           - View all logs"
	@echo "make logs-backend   - View backend logs"
	@echo "make logs-frontend  - View frontend logs"
	@echo "make logs-ollama    - View ollama logs"
	@echo "make logs-qdrant    - View qdrant logs"
	@echo "make clean          - Remove containers and volumes"
	@echo "make pull-models    - Pull Ollama models (llama3:8b, nomic-embed-text)"
	@echo "make status         - Show container status"

build:
	docker compose build

up:
	docker compose up -d
	@echo ""
	@echo "✅ All services started!"
	@echo ""
	@echo "Services available at:"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Ollama:   http://localhost:11434"
	@echo "  Qdrant:   http://localhost:6333"
	@echo ""
	@echo "Run 'make logs' to see logs"

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

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

# Development shortcuts
dev-backend-logs:
	docker compose logs -f backend

dev-frontend-logs:
	docker compose logs -f frontend

shell-backend:
	docker compose exec backend /bin/bash

shell-frontend:
	docker compose exec frontend /bin/sh
