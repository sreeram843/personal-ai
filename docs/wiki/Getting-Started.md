# Getting Started

## Prerequisites

- Docker + Docker Compose (recommended path)
- Or: Python 3.11+, Node 20+, local Postgres / Qdrant / Ollama / Redis
- Git

## Clone

```bash
git clone https://github.com/sreeram843/personal-ai.git
cd personal-ai
cp .env.example .env
```

For production-shaped local cloud chat:

```bash
cp .env.cloud.example .env.cloud
# edit secrets, ADMIN_EMAILS, Google OAuth, Caddy domains as needed
```

## Fastest path: Docker Compose (local)

```bash
docker compose up --build
```

Typical local URLs:

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Frontend (Vite, if run separately) | http://localhost:5173 |
| Ollama | http://localhost:11434 |
| Qdrant | http://localhost:6333 |
| Redis | redis://localhost:6379/0 |

Pull the embed model once Ollama is up:

```bash
curl http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}'
```

See [Compose Profiles](Compose-Profiles) for `cloud-chat`, `workers`, observability, and GPU stacks.

## Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Point the UI at the API via Vite proxy / `VITE_*` settings used in the repo. For local auth bypass:

```bash
AUTH_DISABLED=true
```

## Backend without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ensure Postgres, Qdrant, Ollama, Redis are reachable
alembic upgrade head
uvicorn app.main:app --reload
```

## Smoke checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -I http://localhost:8000/metrics
```

With auth disabled, try chat completions:

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"curai-default","messages":[{"role":"user","content":"hello"}]}'
```

## Next

- [Architecture](Architecture) — how a request flows
- [Configuration](Configuration) — env flags that matter
- [Authentication](Authentication) — turn on Google login
- [Testing and Quality](Testing-and-Quality) — run the quality gate
