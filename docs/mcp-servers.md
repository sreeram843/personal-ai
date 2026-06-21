# MCP servers (remote-first)

Cursor reads **`.cursor/mcp.json`** (gitignored). Copy the template and add your tokens:

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
```

Then **Cursor → Settings → Tools & MCP → reload**.

Penpot setup details: [penpot-mcp.md](penpot-mcp.md).

---

## Strategy

Use **hosted HTTP MCP** wherever a free or official remote exists. Keep **stdio** only when there is no practical remote (local Chrome, project knowledge graph).

| Server | Transport | Remote? | Token |
|--------|-----------|---------|-------|
| **penpot** | HTTP | Yes | Penpot MCP key (you have this) |
| **supabase** | HTTP | Yes | OAuth in Cursor UI, or PAT (optional) |
| **github** | HTTP | Yes | GitHub PAT (`repo` scope) |
| **chroma-package-search** | HTTP | Yes | Chroma API key from [trychroma.com/package-search](https://trychroma.com/package-search) |
| **code-review-graph** | stdio | No | — (project-local Python) |
| **chrome-devtools** | stdio | No | — (controls your local Chrome) |

**Removed from default config** (replaced by remotes or optional):

- `postgres`, `supabase-local` → use **supabase** remote
- `git` (Docker) → use **github** remote
- `chroma` (local uvx), `pglite` → optional; see [`.cursor/mcp.local.optional.json.example`](../.cursor/mcp.local.optional.json.example)
- `sequential-thinking` → optional local; no official free hosted remote

---

## Tokens you need

### Already configured

| Service | Status |
|---------|--------|
| **Penpot** | In `.cursor/mcp.json` |

### Please provide / configure

| Service | How to get it | Where to put it |
|---------|---------------|-----------------|
| **GitHub** | [github.com/settings/tokens](https://github.com/settings/tokens) — classic PAT with `repo` (or fine-grained repo read) | Replace `YOUR_GITHUB_PAT` in `.cursor/mcp.json` → `github.headers.Authorization` |
| **Supabase** | Optional: [supabase.com/dashboard/account/tokens](https://supabase.com/dashboard/account/tokens) | Add `headers.Authorization: Bearer YOUR_PAT` if OAuth does not work; scope with `?project_ref=YOUR_REF` on the URL |
| **Chroma package search** | [trychroma.com/package-search](https://trychroma.com/package-search) → API key | Replace `YOUR_CHROMA_API_KEY` in `chroma-package-search.headers.x-chroma-token` |

**Supabase OAuth:** Cursor may open a browser login on first connect to `https://mcp.supabase.com/mcp` — no PAT required if that flow succeeds.

**Disable unused remotes** in Settings → Tools & MCP if you hit the ~40-tool cap (e.g. skip `chroma-package-search` until you have a key).

---

## Remote servers

### Penpot

```json
"penpot": {
  "url": "https://design.penpot.app/mcp/stream?userToken=YOUR_PENPOT_MCP_KEY",
  "type": "http"
}
```

### Supabase (cloud)

Read-only by default:

```json
"supabase": {
  "url": "https://mcp.supabase.com/mcp?read_only=true",
  "type": "http"
}
```

Single project:

```json
"url": "https://mcp.supabase.com/mcp?project_ref=YOUR_PROJECT_REF&read_only=true"
```

With PAT (CI / no OAuth):

```json
"headers": { "Authorization": "Bearer YOUR_SUPABASE_ACCESS_TOKEN" }
```

### GitHub (replaces local git Docker)

Read-only Copilot MCP endpoint:

```json
"github": {
  "url": "https://api.githubcopilot.com/mcp/readonly",
  "type": "http",
  "headers": { "Authorization": "Bearer YOUR_GITHUB_PAT" }
}
```

Full read/write: use `https://api.githubcopilot.com/mcp/` instead of `/readonly`.

### Chroma package search (remote)

Semantic search over public packages — not the same as local RAG `chroma-mcp`:

```json
"chroma-package-search": {
  "url": "https://mcp.trychroma.com/package-search/v1",
  "type": "http",
  "headers": { "x-chroma-token": "YOUR_CHROMA_API_KEY" }
}
```

For **Chroma Cloud** as your vector DB (Phase 1+), you still use `uvx chroma-mcp --client-type cloud` with tenant/database/API key — see optional local config.

---

## Local-only servers

### code-review-graph

Project knowledge graph. Path in `.cursor/mcp.json` must point at your `code_review_graph` venv Python.

### chrome-devtools

```bash
npx -y chrome-devtools-mcp@latest --help
```

Requires Chrome. Complements **IronBee DevTools** (Playwright); disable one if tool limits are hit.

---

## Optional local servers

Copy entries from [`.cursor/mcp.local.optional.json.example`](../.cursor/mcp.local.optional.json.example) into `.cursor/mcp.json` when needed:

- **sequential-thinking** — free local reasoning helper
- **postgres** — direct SQL if not using Supabase MCP
- **supabase-local** — `supabase start` → `http://127.0.0.1:54321/mcp`
- **chroma-local** / **pglite** — embedded stores under `memory/` (gitignored)
- **git-local** — Docker `mcp/git` on repo bind-mount

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| GitHub 401 | Regenerate PAT; confirm `Bearer ` prefix in header |
| Supabase auth failed | Try OAuth reconnect in MCP settings, or add PAT header |
| Chroma 401 | Issue key at package-search; check `x-chroma-token` header name |
| `spawn npx ENOENT` | Use full path from `which npx` |
| Too many tools | Disable chrome-devtools or chroma-package-search |
| Penpot disconnect | Regenerate MCP key in Penpot profile |

---

## Related

- [penpot-mcp.md](penpot-mcp.md)
- [roadmap.md](roadmap.md) — Phase 1 Postgres / Supabase for app persistence
