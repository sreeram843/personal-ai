# Copilot Code Review Guidelines

The following instructions apply when performing code reviews for this personal AI chatbot project.

## General Guidelines

- [ ] Code is readable and well-commented
- [ ] No hardcoded values (API keys, URLs, sensitive data)
- [ ] Error handling is present and meaningful
- [ ] Performance impact is considered

---

## Frontend Code Review (React/TypeScript/Vite)

**File patterns:** `frontend/src/**/*.{tsx,ts,css}`

### React Components
- [ ] Component is functional (hooks-based, not class component)
- [ ] Props are properly typed with TypeScript interfaces
- [ ] `useEffect` dependencies are correct (avoids infinite loops)
- [ ] No direct DOM manipulation (use React refs only when necessary)
- [ ] Component is testable and has a single responsibility

### TypeScript
- [ ] No `any` types used (prefer specific types or generics)
- [ ] Imports are organized (React first, then third-party, then local)
- [ ] Types are exported from shared type files (`frontend/src/types.ts`)
- [ ] Interfaces/types are named with PascalCase

### Styling (Tailwind CSS)
- [ ] Uses TailwindCSS classes (not inline styles)
- [ ] Responsive classes applied (sm:, md:, lg:, xl:)
- [ ] Component respects dark/light theme variables
- [ ] No hardcoded colors—use CSS variables from `index.css`

### Frontend UI
- [ ] Light/dark theme and accent (phosphor) toggles work correctly
- [ ] Chat input, voice, and attach actions work without layout issues
- [ ] Web Audio feedback (optional key/send sounds) does not block the UI

---

## Backend Code Review (FastAPI/Python)

**File patterns:** `app/**/*.py`, `api/**/*.py`

### FastAPI Endpoints
- [ ] Route has appropriate HTTP method (GET, POST, PUT, DELETE)
- [ ] Request/response models use Pydantic schemas (`app/schemas/*.py`)
- [ ] CORS settings are appropriate
- [ ] Status codes are correct (200, 201, 400, 404, 500)
- [ ] Error responses include meaningful messages

### Python Code Style
- [ ] Follows PEP 8 (4-space indentation, snake_case for variables)
- [ ] Type hints on function signatures (Python 3.11+)
- [ ] Docstrings on functions/classes
- [ ] No hardcoded values—use `config.py` or environment variables
- [ ] Imports grouped: standard library, third-party, local (alphabetical)

### Persona/System Prompts
- [ ] Persona and system instructions are clear and consistent
- [ ] API responses return plain `message` text (readable in any chat UI)
- [ ] User-facing error copy is short and clear (avoid cryptic error codes in the default path)

### Ollama/Qdrant Integration
- [ ] Health checks for external services are in place
- [ ] Graceful fallback if Ollama/Qdrant unavailable
- [ ] Vector store operations handle errors properly
- [ ] Document ingestion validates file types and sizes

---

## Docker & Deployment

**File patterns:** `Dockerfile*`, `docker-compose.yml`, `.github/workflows/*.yml`

### Dockerfile
- [ ] Multi-stage build optimizes image size
- [ ] Frontend (Node) stage builds React correctly
- [ ] Python stage installs dependencies cleanly
- [ ] Final image is as small as possible
- [ ] No secrets or credentials in image

### Docker Compose
- [ ] All services (app, ollama, qdrant) have proper depends_on
- [ ] Ports are correctly mapped (8000 for app, 11434 for Ollama, 6333 for Qdrant)
- [ ] Environment variables passed to services
- [ ] Volumes mounted for persistent data (Qdrant collections)
- [ ] Health checks for critical services

### Deployment (ngrok/production)
- [ ] API base URL is correctly resolved for remote hosts
- [ ] Safari/mobile fetch fallback is in place
- [ ] No localhost hardcoded in production bundles
- [ ] CORS origins whitelist production domain

---

## API Client Review (frontend/src/api.ts)

- [ ] `resolveBaseUrl()` detects localhost vs remote correctly
- [ ] `safeFetch()` retries on network errors for Safari
- [ ] Error responses are handled gracefully
- [ ] Request/response cycles include appropriate timeouts
- [ ] No credentials exposed in logs or console

---

## Documentation & Examples

- [ ] README.md updated with new features or changes
- [ ] Code comments explain "why", not "what"
- [ ] Complex algorithms have explanatory comments
- [ ] Examples provided for new endpoints or components
- [ ] Troubleshooting section updated if applicable

---

## Testing & Validation

- [ ] Changes tested locally with `docker compose up`
- [ ] Frontend builds: `npm run build` (no errors/warnings)
- [ ] Backend syntax valid: `python -m py_compile app/**/*.py`
- [ ] Docker build passes: `docker compose up --build`
- [ ] API endpoints verified with curl or similar tool
- [ ] Primary chat UI flows tested (empty state, send, settings)

---

## Performance & Security

- [ ] No N+1 queries or excessive API calls
- [ ] Frontend bundle size impact assessed
- [ ] Python dependencies audit for security issues
- [ ] No sensitive data logged or exposed
- [ ] CORS headers are restrictive (not wildcard for production)

---

## Common Issues to Watch For

1. **API Base URL Problems**: Always use `resolveBaseUrl()` for cross-origin requests
2. **Safari Fetch Errors**: Ensure `safeFetch()` is used for network calls
3. **Docker Build Failures**: Verify Node build stage completes before Python stage
4. **Ollama Connectivity**: Ensure service is healthy before making inference calls
5. **Phosphor Theme Sync**: Verify theme state persists across page refreshes

---

## File Naming Conventions

- React components: `PascalCase.tsx` (e.g., `ChatInput.tsx`)
- Utilities: `camelCase.ts` (e.g., `terminalAudio.ts`)
- Python modules: `snake_case.py` (e.g., `persona_manager.py`)
- Styles: Inline with Tailwind, or `kebab-case.css` (e.g., `crt-screen.css`)
- Configuration: `config.py` (FastAPI), `tsconfig.json` (TypeScript)

---

## PR Review Checklist Summary

Before approving, ensure:
- ✅ Code quality meets standards above
- ✅ Tests/validation performed locally
- ✅ Docker builds and runs
- ✅ API endpoints verified
- ✅ UI renders correctly (both modes)
- ✅ Documentation updated
- ✅ No breaking changes (or documented if necessary)

# Code Graph MCP — Context Instructions

## IMPORTANT: Always scope your context before acting

Before answering any question or performing any task in this repository,
call the `pareto_context_graph` MCP tool to get relevant context.

### How to use:

1. Identify which file(s) the user is asking about or working in.
2. Call `pareto_context_graph` with command="context" and those file paths:
   ```json
   {"command": "context", "files": ["path/to/file.rb"], "query": "user's question", "tier": 1}
   ```
3. Tier 1 (default) gives summaries. If you need more detail on specific files,
   call again with tier=2 (signatures) or tier=3 (code chunks).
4. On follow-up prompts, pass `already_have` with files you already read:
   ```json
   {"command": "context", "files": [...], "already_have": ["file1.rb", "file2.rb"]}
   ```
5. Start a **new task** with a fresh session — call `session_clear` or
   `pareto-context-graph session clear` so stale paths are not auto-merged:
   ```json
   {"command": "session_clear"}
   ```
6. Do NOT scan, grep, or read other files unless the tool's results are insufficient.

### Why:
This repository has a co-change graph built from git history plus import/keyword analysis.
The tool identifies the files most likely to matter — ones that provably changed together,
share imports, or follow naming conventions — so you read the right files, not random ones.
Less noise = fewer hallucinations = more accurate answers.

### Tiers:
- tier=1: File paths + 1-line summaries (cheapest, use for orientation — ~30 tokens/file)
- tier=2: Function/class signatures (use when you need API shape)
- tier=3: Relevant code chunks (use when you need implementation details)

### Delta context (multi-turn):
On follow-up prompts, always pass `already_have` with files already in the conversation.
This skips redundant re-reads and keeps each turn focused on new context only.
For a **new user task**, call `session_clear` first (or CLI: `pareto-context-graph session clear`).

### Token budgets:
Install the tiktoken extra for honest budgets: `pip install -e '.[tiktoken]'`.
Use `diagnostics: true` on context for per-candidate score breakdown.
Every `context` response includes `suggested_next` (tier escalation / compression hints).

### Other commands:
- `search` — Find files by name/path (e.g. `{"command": "search", "query": "patient"}`)
- `neighbours` — Co-change neighbours for a file (e.g. `{"command": "neighbours", "path": "app/models/patient.rb"}`)
- `blast` — Files affected by current git diff
- `stats` — File/edge counts for the graph
- `hotspots` — Most co-changed files (top N)
- `communities` — Detected file clusters (architectural modules)
