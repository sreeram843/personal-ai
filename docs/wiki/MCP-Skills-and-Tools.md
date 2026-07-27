# MCP Skills and Tools

## In-product tools

The **tool agent** (`ENABLE_TOOL_AGENT=true`, model `curai-tools`) can call registered tools exposed via:

- `GET /tools?role=chat_agent`
- Skill binding via `assistant_id` on chat / `/v1` requests

Skills and prompts live under the app (see `app/prompts/` and skill-related services). Prefer the governed single-assistant model (personas removed in Phase 0).

## Developer MCP (Cursor)

Repo template: `.cursor/mcp.json.example` → copy to `.cursor/mcp.json` (gitignored).

Strategy: **hosted HTTP MCP** when available; stdio only when necessary.

| Server | Transport | Notes |
|--------|-----------|-------|
| penpot | HTTP | Design tooling |
| github | HTTP | PAT with `repo` |
| supabase | HTTP | OAuth or PAT |
| chroma-package-search | HTTP | Package search key |
| code-review-graph | stdio | Project knowledge graph |
| chrome-devtools / IronBee | local | Browser verification |

Full token checklist: in-repo `docs/mcp-servers.md`, Penpot: `docs/penpot-mcp.md`.

## IronBee DevTools

This workspace uses IronBee browser MCP for UI verification (navigate → ARIA snapshot → interact → screenshot). Prefer `execute` for multi-step flows. See `.cursor/rules/ironbee-devtools-use.mdc`.

## Related

- [Chat and Routing](Chat-and-Routing)
- [API Reference](API-Reference)
- [Frontend and UI](Frontend-and-UI)
