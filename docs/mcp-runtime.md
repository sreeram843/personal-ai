# Runtime MCP connectors

Per-user **HTTP** Model Context Protocol (MCP) servers that CurieAI discovers at
chat time and injects as tools for **that session only**. This is product
runtime MCP — not Cursor IDE MCP.

| Surface | Doc |
|---------|-----|
| In-app connectors (this document) | Settings → Agent → MCP; `app/api/mcp_routes.py` |
| Cursor / IDE servers | [mcp-servers.md](./mcp-servers.md) |
| Decision record | [adr/0007-runtime-mcp-connectors.md](./adr/0007-runtime-mcp-connectors.md) |
| Wrapping sibling repos as MCP servers | [mcp-tool-federation.md](./mcp-tool-federation.md) |

Gated by `ENABLE_RUNTIME_MCP` (default `true`). Connect timeout:
`MCP_CONNECT_TIMEOUT` (default 20s). Implementation:
`app/services/mcp_store.py`, `mcp_client.py`, `mcp_tools.py`; chat wiring in
`app/services/chat_execution.py` (`agent_runtime_session`).

---

## Per-user registration

A signed-in user registers an HTTP MCP endpoint from **Settings → Agent → MCP**.
The backend stores records in a JSON file under `memory/` (default
`memory/mcp_servers.json`, override `MCP_SERVERS_PATH`). Each record is tagged
with `user_id`; list/get/update/delete all require that id.

Fields written on create (`POST /mcp/servers`, schema `McpServerCreate`):

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | 1–80 chars |
| `url` | yes | HTTP MCP URL (streamable HTTP / JSON-RPC). No stdio. |
| `enabled` | no | Default `true`. Disabled servers are skipped at discovery. |
| `headers` | no | Optional request headers (UI sends `Authorization` when a token is entered). |

Responses use `McpServerResponse`: id, name, url, enabled, **`header_keys`**
(sorted names only), last_status / last_error / tool_count / last_checked_at.
Header **values are never returned**. HTTP verbs: [api.md](./api.md) (Runtime
MCP). Auth is the same JWT `CurrentUser` as the rest of the app. There is no
admin router for MCP and no global connector catalog.

The Settings form defaults the URL to GitHub Copilot's read-only MCP
(`https://api.githubcopilot.com/mcp/readonly`) so a first-time smoke does not
require inventing an endpoint. See [Read-only smoke](#read-only-smoke).

---

## Namespacing and session injection

`mcp_tool_id(server_id, tool_name)` in `app/services/mcp_tools.py` builds:

```
mcp_{server_id}_{sanitized_tool_name}
```

`server_id` is the UUID from the store. `tool_name` is lowercased and stripped
to `[a-zA-Z0-9_]`. Prefix is always `mcp_`. Display name is
`{server.name}: {tool.name}`; description is tagged `[MCP:{server.name}]`.

On each agent chat run, `agent_runtime_session` calls
`discover_user_mcp_tools` for that `user_id`, then
`ToolRegistry.activate_session_tools(...)`. The overlay is a `ContextVar` —
it does **not** mutate the process-wide builtin registry. The `finally` block
deactivates the overlay when the request ends.

Discovery skips servers that are disabled or have an empty URL. Failures are
recorded on the store (`last_status=error`) and omitted from the overlay; other
servers still load. Role is `chat_agent` only
(`CHAT_AGENT_ROLE`). Spec timeout is 45s; max output 12 000 chars.

Remote `inputSchema` is kept on `McpToolDefinition` for listing. The LLM sees
the same generic function schema as other chat tools (`query` / `user_query`,
`additionalProperties: true` in `build_openai_tool_definitions`). The executor
forwards the model's argument dict to `tools/call` (drops `user_id`).

---

## Scope

Connectors are **per-user, not global**. Isolation is the `user_id` filter on
every store method — the same tenant rule as [ADR 0005](./adr/0005-per-user-tenant-isolation.md),
applied to a file-backed list rather than Postgres.

There are no platform-admin MCP connectors, no shared org catalog, and no
stdio/local-process servers in the product runtime. `GET /tools` and the
Doctor panel list the **global** registry; they do not activate a user's MCP
overlay, so those surfaces will not show `mcp_*` tools unless a session is
active.

Doctor (`GET /agent/diagnostics`) reports whether runtime MCP is enabled and
how many of *that user's* servers last connected.

---

## Read-only smoke

The MCP tab pre-fills:

- Name: `GitHub`
- URL: `https://api.githubcopilot.com/mcp/readonly`

That is GitHub Copilot's **read-only** hosted MCP. Add an `Authorization`
token if the endpoint requires one (the UI prefixes `Bearer ` when the value
does not already start with it). Use **Test** (`POST .../test`) to confirm
`tools/list` before chatting.

A successful test writes `last_status=connected` and `tool_count`. Chat then
discovers those tools into the session overlay. Prefer this read-only URL for
smoke; the full Copilot MCP (`https://api.githubcopilot.com/mcp/`) is a
different, write-capable endpoint.

---

## Security model

### Approval (`tool_permissions.py`)

MCP specs set `requires_approval` from name/description heuristics (below).
Independently, `tool_requires_user_approval` treats any `mcp_*` tool that is
**not** heuristically read-only as needing approval.

How that interacts with `ChatAgentOptions.tool_permission_mode`:

| Mode | Write / unknown MCP tool |
|------|--------------------------|
| `ask` | Pauses (`needs_approval`) until the client resends with `approved_tool_ids` |
| `plan` | Records a planned call; does not execute |
| `auto` | Executes and stamps `approved_by` as `auto:{user_id}` |

Read-hint tools still run in `ask` without a prompt, unless the spec itself
sets `requires_approval`.

### Sandbox (`sandbox_policy.py`)

`ToolRegistry.invoke_tool` always runs `SandboxPolicyEnforcer.validate_invocation`
then `execute_with_policy` (role check, optional path/command allowlists, output
truncation, audit log). MCP tools are `ToolRiskClass.NETWORK` with
`NETWORK_REQUEST`; they do not set `allowed_domains`. Sandbox is a backstop for
role and I/O policy, not an SSRF allowlist.

### Trusted-user-supplied URLs

Users may register **any** URL. The API process POSTs to it (`McpHttpClient`,
JSON-RPC, `follow_redirects=True`) using stored headers. Treat connectors as
**trusted-user-supplied endpoints**: the user is authorizing the server to call
that URL on their behalf. Header values stay on disk and in request headers;
API responses expose `header_keys` only.

### SSRF

There is no private-IP / metadata-IP block and no host allowlist. A connector
URL is fetched **server-side**, so a user who can register MCP servers can
cause the CurieAI host to call addresses the browser could not (link-local,
RFC1918, cloud metadata, internal admin ports). Operate on that assumption:

- Do not point connectors at internal services you would not give that user.
- Prefer public, token-gated MCP hosts; keep tokens in headers, not in the URL
  if the URL is echoed in list responses (URLs **are** returned).
- On shared or multi-tenant hosts, treat MCP registration as a privileged
  network capability.

### Risk-class heuristics (`mcp_tools.py`)

Every MCP tool is `ToolRiskClass.NETWORK`. `_risk_for_mcp_tool` scans
`tool_name + description` (lowercased):

| Heuristic | `requires_approval` |
|-----------|---------------------|
| Read hints: `get_`, `list_`, `search_`, `read_`, `fetch_`, `lookup_`, `find_`, `query_` | `false` |
| Write hints: `create_`, `update_`, `delete_`, `write_`, `post_`, `push_`, `merge_`, `deploy_` | `true` |
| Neither (unknown) | `true` |

`tool_permissions._is_read_only_tool` uses a similar read list **without**
`query_`, plus `ToolRiskClass.SAFE`. Unknown and write-shaped names require
approval; names that only match `query_` may still hit the `mcp_*` prefix gate.

These heuristics are **not** a substitute for a read-only MCP server. A tool
named `list_and_delete` can look like a read. Prefer endpoints that are
read-only at the server (the Copilot `/readonly` URL) when smoking.

---

## Out of scope

This product only **registers** HTTP URLs the user provides. Wrapping sibling
repos (stock-pred-model, curie-fhir, curie-prediction-pipeline) as those URLs
is supply-side work — see [mcp-tool-federation.md](./mcp-tool-federation.md).

Also not in this design: stdio MCP, admin-wide connectors, forwarding remote
`inputSchema` into `ToolSpec`, or SSRF hardening beyond the documentation
above.
