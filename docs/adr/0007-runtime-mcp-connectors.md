# 0007 — Per-user runtime MCP connectors

Status: Accepted

## Context

CurieAI's chat agent already has a `ToolRegistry` with role checks, sandbox
policy, and permission modes (`auto` / `ask` / `plan`). Users also run MCP
servers in **Cursor** via `.cursor/mcp.json` ([mcp-servers.md](../mcp-servers.md)),
which never reaches the product backend.

Phase C (GitHub issue #12) asked for in-app MCP so a logged-in user can attach
remote tools to **their** chat session, with auth and sandboxing. Alternatives
considered:

- **Global / admin connectors** — one catalog for the deployment. Conflicts with
  per-user tenant isolation ([0005](0005-per-user-tenant-isolation.md)) and
  would mix credentials across tenants.
- **IDE-only MCP** — already works; does not help the hosted assistant.
- **stdio servers spawned by the API process** — couples CurieAI to local
  binaries and a larger sandbox surface.
- **Wrapping sibling repos as first-party MCP servers** — supply-side; tracked
  separately as issue #42.

## Decision

Register **per-user HTTP MCP connectors in-app** (Settings → Agent → MCP).
Persist URL + optional headers in a file-backed store under `memory/`, scoped
by `user_id`. Discover tools at chat time and **session-inject** them into
`ToolRegistry` (`mcp_{server_id}_{tool}` ids) without mutating the global
builtin set.

Write and unknown MCP tools **require approval** (`requires_approval` on the
spec plus the `mcp_*` gate in `tool_permissions.py`). `ask` pauses until
`approved_tool_ids`; `plan` does not execute; `auto` executes with an
`auto:{user_id}` audit stamp. Sandbox policy still wraps every invoke.
Treat registered URLs as trusted-user-supplied; never return header values
(only `header_keys`).

Design: [mcp-runtime.md](../mcp-runtime.md).

## Consequences

- Users can extend chat tools without a deploy or admin catalog; isolation is
  per `user_id` on the store and per-request session overlay.
- The API host performs server-side HTTP to arbitrary user URLs (SSRF class).
  Operators must treat MCP registration as a network capability; there is no
  private-IP allowlist in code.
- Heuristic read vs write classification can mis-label tools; prefer
  server-enforced read-only endpoints for smoke (Copilot `/mcp/readonly`).
- Sibling-repo federation stays out of this ADR (issue #42).
