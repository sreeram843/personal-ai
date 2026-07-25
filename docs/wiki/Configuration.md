# Configuration

Copy examples; never commit real secrets.

| File | Purpose |
|------|---------|
| `.env.example` → `.env` | Local / default Docker |
| `.env.cloud.example` → `.env.cloud` | Production cloud-chat on VM |
| `.env.remote.example` | Remote / alternate hosts |
| `.env.gpu-vllm.example` | GPU + vLLM profile |

## Chat execution

```bash
ENABLE_FAST_CHAT=true
ENABLE_TOOL_AGENT=true
ENABLE_OPENAI_API=true
```

## Auth

```bash
AUTH_DISABLED=true          # local only
AUTH_SIGNUP_MODE=invite
ADMIN_EMAILS=you@gmail.com
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
SETTINGS_SECRET_KEY=...     # Fernet for provider secrets
```

## LLM / Ollama

```bash
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=llama3:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
LLM_DEFAULT_PROVIDER=ollama
LLM_DEFAULT_MODEL=llama3:8b
# Optional OpenAI-compatible:
LLM_OPENAI_BASE_URL=
LLM_OPENAI_API_KEY=
# Per-stage overrides: LLM_PLANNER_*, LLM_SYNTHESIZER_*, LLM_REVIEWER_*, LLM_WRITER_*
```

## Qdrant / retrieval

```bash
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=personal_ai_documents
EMBEDDING_DIMENSION=768
DEFAULT_TOP_K=4
RETRIEVAL_HYBRID_ENABLED=true
# Optional cross-encoder (off by default):
# RETRIEVAL_CROSS_ENCODER_ENABLED=true
# RETRIEVAL_CROSS_ENCODER_PROVIDER=http
# RETRIEVAL_CROSS_ENCODER_URL=http://reranker:80
```

## Ingest

```bash
# INGEST_ALLOWED_EXTENSIONS=.txt,.md,.pdf
# INGEST_MAX_DOCUMENT_BYTES=512000
# INGEST_MAX_UPLOAD_BYTES=10000000
ENABLE_BACKGROUND_WORKERS=false
WORKER_QUEUE_BACKEND=arq
```

## Cache / Redis

```bash
ENABLE_ADAPTER_CACHE=true
ADAPTER_CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

## CORS / demo

```bash
CORS_ORIGINS=http://localhost:5173,...
DEMO_ENABLED=false
# DEMO_EMBED_ALLOWED_ORIGINS=https://yourname.dev
```

## Caddy (prod)

Set in `.env.cloud` (see `docs/prod-gcp-vm.md`):

- `CADDY_DOMAIN` / chat domain
- `CADDY_ADMIN_DOMAIN`
- Email for ACME, etc.

## Related

- [Compose Profiles](Compose-Profiles)
- [Deployment](Deployment)
- [Admin Portal](Admin-Portal)
