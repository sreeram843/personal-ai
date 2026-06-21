# Penpot MCP setup

[Penpot MCP](https://help.penpot.app/mcp/) connects AI agents to Penpot design files for design-to-code and design maintenance workflows.

**Default in this repo:** remote Penpot SaaS (`design.penpot.app`). Figma MCP has been removed.

---

## Cursor MCP configuration (two places)

Cursor reads MCP servers from **two JSON files** and from **Settings → Tools & MCP**:

| Scope | File | Use for |
|-------|------|---------|
| **Project** | `.cursor/mcp.json` | All MCPs including **Penpot remote**, git, postgres, etc. |
| **Global** (optional) | `~/.cursor/mcp.json` | Penpot across all projects (duplicate of project entry is fine) |

Open **Cursor Settings** (`Cmd + ,`) → **Tools & MCP** to see connection status, enable/disable servers, and open the config file (**Add MCP server** / **New MCP Server**).

After editing any `mcp.json`, **reload MCP** or restart Cursor.

### First-time setup

```bash
# Project servers (edit python path for code-review-graph)
cp .cursor/mcp.json.example .cursor/mcp.json

# Global Penpot (paste URL from Penpot Integrations)
# Edit ~/.cursor/mcp.json — see example below
```

**`~/.cursor/mcp.json`** (global — your token, not in git):

```json
{
  "mcpServers": {
    "penpot": {
      "url": "https://design.penpot.app/mcp/stream?userToken=YOUR_MCP_KEY",
      "type": "http"
    }
  }
}
```

Copy the full URL from **Penpot → Your account → Integrations → MCP Server → Copy link**.

**`.cursor/mcp.json`** (project — gitignored, paths are machine-specific):

```json
{
  "mcpServers": {
    "code-review-graph": {
      "command": "/path/to/python3.12",
      "args": ["-m", "code_review_graph", "serve"],
      "type": "stdio"
    }
  }
}
```

Legacy root `.mcp.json` is still supported by some tools but **Cursor prefers** `.cursor/mcp.json` + `~/.cursor/mcp.json`.

---

## Connect Penpot in the browser

1. Open [design.penpot.app](https://design.penpot.app) and a design file.
2. **File → MCP Server → Connect**
3. Confirm **Connected**.

No local `npx @penpot/mcp` server is needed for **remote** mode.

---

## Verify in Cursor

1. **Settings → Tools & MCP**
2. You should see **penpot** (global) and **code-review-graph** (project) with green/connected status.
3. Test: *"List pages in this Penpot file."*

---

## Local Penpot MCP (optional)

```bash
make penpot-mcp
```

Use `"url": "http://localhost:4401/mcp"` in `~/.cursor/mcp.json` and load the plugin from `http://localhost:4400/manifest.json`.

---

## Security

- Never commit `~/.cursor/mcp.json`, `.cursor/mcp.json`, or root `.mcp.json` if they contain tokens or local paths you care about.
- Regenerate your Penpot MCP key if it was exposed.

## References

- [Penpot MCP help](https://help.penpot.app/mcp/)
- [Cursor + Penpot setup](https://penpot.app/blog/set-up-penpot-mcp-with-cursor-in-5-steps-and-no-code/)
