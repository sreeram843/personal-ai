# Roadmap

Phases **0–3 are complete** in the product plan. Canonical detail: in-repo `docs/roadmap.md`.

## Goals (unchanged)

| Goal | Outcome |
|------|---------|
| Scalability | Stateless API, DB state, workers |
| Multi-user | Auth, per-user RAG, server history |
| Simpler product | Single governed assistant |
| Better UX | Synced conversations, streaming |
| Live data | Intent routing, adapters, TTLs |
| Cloud deploy | Probes, Helm/Terraform, split embed vs chat |

## LLM preference

- **Embeddings:** local Ollama (`nomic-embed-text`) or DMR embed
- **Chat:** Ollama **or** OpenAI-compatible (vLLM, Groq, etc.)
- **Orchestration:** `OrchestratedChatService` + `LLMGateway` per-stage routing

## Phase overview

```
Phase 0 Foundation → Phase 1 Multi-user → Phase 2 Scale/cloud → Phase 3 Polish
```

| Phase | Focus | Status |
|-------|--------|--------|
| 0 | Personas removed, system prompt file, health/ready | Done |
| 1 | Postgres, auth, conversations, tenant ingest | Done |
| 2 | React Query UI, workers, Helm, GPU profiles | Done |
| 3 | Live intent router, adapter upgrades, Terraform | Done |

## Recent hardening (post Phase 3)

Documented in this wiki under [RAG and Retrieval](RAG-and-Retrieval):

- PDF ingest
- Citation preservation through writer
- Optional cross-encoder rerank
- Hybrid dense + keyword retrieval
- Web evidence scoring + weather/FX fallbacks
- Retrieval golden eval (recall@k / MRR)

## Ideas for later

Track in GitHub Issues; examples:

- Broader retrieval golden coverage
- Default-on cross-encoder in prod if latency budget allows
- Deeper admin analytics
- Mobile (Capacitor) polish

## Related

- [Architecture](Architecture)
- [Home](Home)
