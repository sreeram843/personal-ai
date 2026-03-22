# Docker Setup Guide

## Overview

The project is now containerized with Docker Compose for easy local development and deployment. All services (Backend, Frontend, Ollama, Qdrant) run in separate containers with automatic networking.

## Files Created

### Docker Configuration
- **docker-compose.yml** - Main orchestration file with all services
- **Dockerfile.backend** - Backend FastAPI container
- **frontend/Dockerfile** - Frontend React/Vite container
- **.dockerignore** - Exclude unnecessary files from Docker builds

### Scripts
- **start.sh** - Linux/macOS startup script (executable)
- **start.bat** - Windows startup script

### Makefile
- **Makefile** - Convenience commands for docker compose operations

## Quick Start

### Option 1: Using the Startup Script (Easiest)

**Linux/macOS:**
```bash
./start.sh
```

**Windows:**
```bash
start.bat
```

### Option 2: Using Docker Compose Directly

```bash
# Copy environment file
cp .env.example .env

# Build images
docker compose build

# Start all services
docker compose up -d

# Pull Ollama models (after services are running)
docker compose exec ollama ollama pull llama3:8b
docker compose exec ollama ollama pull nomic-embed-text
```

### Option 3: Using Makefile

```bash
make help        # See all available commands
make up          # Start all services
make pull-models # Pull Ollama models
make logs        # View all logs
```

## Services

### Backend (FastAPI)
- **Port**: 8000
- **Image**: Custom Python 3.11 image
- **Features**: Hot reload enabled for development
- **Volume Mount**: `./app` and `./api` for live code changes

### Frontend (React + Vite)
- **Port**: 5173
- **Image**: Node 18 Alpine
- **Features**: Hot reload enabled
- **Volume Mounts**: `./frontend/src`, `./frontend/public`, config files

### Ollama (LLM Runtime)
- **Port**: 11434
- **Image**: Official Ollama image
- **Volume**: `ollama_data` (persisted across restarts)
- **Models**: Needs manual pull via `docker compose exec ollama ollama pull <model>`

### Qdrant (Vector Store)
- **Port**: 6333 (API), 6334 (gRPC)
- **Image**: Official Qdrant image
- **Volume**: `qdrant_storage` (persisted across restarts)

## Environment Variables

Key environment variables in docker-compose.yml:

```
OLLAMA_BASE_URL=http://ollama:11434
QDRANT_URL=http://qdrant:6333
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

To change these, edit `.env` file or modify docker-compose.yml.

## Common Tasks

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f ollama
docker compose logs -f qdrant
```

### Stop Services
```bash
docker compose down
```

### Restart Services
```bash
docker compose restart
```

### Remove Everything (Clean Slate)
```bash
docker compose down -v
```

### Access Container Shell
```bash
# Backend (Python/Bash)
docker compose exec backend /bin/bash

# Frontend (Node/sh)
docker compose exec frontend /bin/sh

# Ollama
docker compose exec ollama /bin/sh

# Qdrant
docker compose exec qdrant /bin/sh
```

### Pull Ollama Models
```bash
# Pull llama3:8b
docker compose exec ollama ollama pull llama3:8b

# Pull embedding model
docker compose exec ollama ollama pull nomic-embed-text

# List all models
docker compose exec ollama ollama list
```

## Health Checks

All services have health checks configured:

- **Ollama**: Checks `/api/tags` endpoint every 10s
- **Qdrant**: Checks `/health` endpoint every 5s
- **Backend**: Depends on both services being healthy

View service health:
```bash
docker compose ps
```

## Performance Tips

1. **First startup** takes longer due to image building
2. **Model pulling** can take 10-30 minutes (depends on internet)
3. **Volume mounts** may be slower on Windows - use WSL2 for better performance
4. **GPU support**: Uncomment GPU settings in docker-compose.yml if you have NVIDIA GPU

## Troubleshooting

### Port Already in Use
**Error**: `Port 5173 is already in use`

**Solution**: Change port in docker-compose.yml or stop other services:
```bash
docker compose down
```

### Out of Disk Space
**Error**: `no space left on device`

**Solution**: Clean up Docker volumes:
```bash
docker system prune -a
docker volume prune
```

### Services Won't Start
**Error**: `failed to get console mode for stdout: The handle is invalid`

**Solution** (Windows): Use WSL2 backend instead of Hyper-V

### Models Not Available
**Error**: `model not found` or `404`

**Solution**: Pull models manually:
```bash
docker compose exec ollama ollama pull llama3:8b
docker compose exec ollama ollama pull nomic-embed-text
```

### Frontend Shows "Cannot Connect to Backend"

**Solution**: Wait for services to be healthy:
```bash
docker compose ps
```

All services should show "healthy" or "running"

## Next Steps

1. Start services with `./start.sh` or `docker compose up -d`
2. Wait for all services to be healthy
3. Open http://localhost:5173
4. Pull Ollama models: `docker compose exec ollama ollama pull llama3:8b`
5. Upload documents or start chatting!

## Production Deployment

For production, consider:
- Building separate production images with multi-stage builds
- Using environment variables for all configuration
- Adding container health checks and monitoring
- Using container orchestration (Kubernetes) for scaling
- Implementing SSL/TLS for secure communication
- Using managed services for Qdrant and/or Ollama

Contact the team for production deployment guidelines.
