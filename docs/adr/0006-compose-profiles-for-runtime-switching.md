# 0006 — Compose profiles for runtime switching

Status: Accepted

## Context

Chat and embeddings must be runnable against several backends — local Ollama, a
cloud OpenAI-compatible API, a GPU vLLM server, or a remote LM Studio host —
without changing application code.

## Decision

Use Docker Compose profiles (`local`, `cloud-chat`, `gpu-vllm`, `remote`,
`workers`) to select the LLM runtime, keeping core services (Postgres, Redis,
Qdrant, app, observability) always-on and LLM containers profile-gated.

## Consequences

- Switching runtime is a `make up-<profile>` call; no code or schema changes.
- Embeddings stay on Ollama in most profiles, so RAG works regardless of the chat
  provider.
- More compose overlays to validate (`docker-compose.{cloud,gpu-vllm,remote-inference,caddy}.yml`)
  and document.
