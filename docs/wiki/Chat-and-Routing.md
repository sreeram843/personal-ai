# Chat and Routing

## Product behavior

CurAI answers through one of three strategies, selected by routing logic and (for `/v1`) the requested model id.

| Strategy | Flag / model | Use |
|----------|--------------|-----|
| Fast chat | `ENABLE_FAST_CHAT=true`, `curai-fast` | Low-latency single-shot replies |
| Tool agent | `ENABLE_TOOL_AGENT=true`, `curai-tools` | Tools, MCP, skills |
| Default / orchestrated | `curai-default` | Full workflow + RAG when needed |

## Orchestrated stages

Typical pipeline:

1. **Planner** — plan retrieval / tools / live needs  
2. **Retrieval / tools** — documents, web, live adapters  
3. **Synthesizer** — draft grounded answer  
4. **Reviewer** — quality / safety checks  
5. **Writer** — final prose; **must preserve citation markers**

Stage models can differ (`LLM_PLANNER_*`, `LLM_SYNTHESIZER_*`, `LLM_REVIEWER_*`, `LLM_WRITER_*`) or be set in the admin **Routing** UI.

## LLM gateway

- Default provider often **Ollama** locally
- Cloud / admin: any **OpenAI-compatible** base URL (Groq, Gemini OpenAI surface, DeepSeek, Perplexity Sonar, vLLM, …)
- Runtime adapters registered per enabled admin provider

Retired Groq ids (as of mid-2026) should be avoided; prefer current Groq catalog ids documented in `docs/admin-portal.md`.

## Conversations

- Server-persisted threads in Postgres
- Frontend uses React Query for history and streaming UX
- Optional `latency_ms` on responses (also stored on assistant message metadata)

## OpenAI-compatible API

Same host and JWT as the web app (`ENABLE_OPENAI_API=true`):

- `GET /v1/models` → `curai-default`, `curai-tools`, `curai-fast`
- `POST /v1/chat/completions` — JSON or SSE (`stream: true`)
- Optional `assistant_id` / `metadata.assistant_id` to bind a skill

Point any OpenAI SDK `base_url` at your CurAI host.

## System prompt / traits

Assistant personality is file-driven: `app/prompts/system.md` (seven traits). See in-repo `docs/traits.md`.

## Related

- [Admin Portal](Admin-Portal) — live provider + stage routing
- [RAG and Retrieval](RAG-and-Retrieval)
- [MCP Skills and Tools](MCP-Skills-and-Tools)
- [API Reference](API-Reference)
