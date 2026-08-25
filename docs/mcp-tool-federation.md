# MCP tool federation

Wrap sibling research repos as **HTTP** MCP servers and register them in
CurieAI chat. Product runtime MCP (per-user URLs, session tools) is
[mcp-runtime.md](./mcp-runtime.md). This document is the **supply side**:
servers you can actually point Settings → Agent → MCP at.

No CurieAI core chat/orchestrator changes are required. Discovery still goes
through `mcp_store.py` + `McpHttpClient`; `sandbox_policy.py` wraps every
invoke the same way as builtin tools.

---

## stock-pred-model (shipped)

The sibling repo
[`stock-pred-model`](https://github.com/sreeram843/stock-pred-model) exposes
a stdlib `http.server` MCP endpoint:

```bash
# from CurieAI repo (prefers sibling file, else a compatible stub)
python scripts/mcp_stockpred.py --port 8765

# or from the sibling repo
python /path/to/stock-pred-model/mcp/http_server.py --port 8765
```

JSON-RPC 2.0 over HTTP (`Content-Type: application/json`), protocol
`2024-11-05`: `initialize`, `tools/list`, `tools/call`. Compatible with
`app/services/mcp_client.py`.

### Register

1. Start the server locally (loopback is enough).
2. In CurieAI: **Settings → Agent → MCP** → add a connector:
   - Name: `stockpred`
   - URL: `http://127.0.0.1:8765/`
3. **Test** (`POST /mcp/servers/{id}/test`) should report three tools.
4. Chat with the agent; tools appear as `mcp_{server_id}_get_forecast` (etc.)
   for that user/session only.

The URL is **user-owned**. CurieAI POSTs to it server-side. Do not point this
at an internal service you would not give that user. See [mcp-runtime.md](./mcp-runtime.md)
(Trusted-user-supplied URLs / SSRF).

### Tool names → CLI

Names use a `get_` prefix so `mcp_tools._risk_for_mcp_tool` and
`tool_permissions.tool_requires_user_approval` classify them as **read-ish**
(`ToolRiskClass.NETWORK`, `requires_approval=false`). Bare `forecast` /
`chain` / `report` would **not** match read hints and may need approval in
`ask` mode — that is why the MCP names differ from the CLI verbs.

| MCP tool | CLI mapping |
|----------|-------------|
| `get_forecast` | `stockpred forecast SYMBOL [--horizon N] --no-log` |
| `get_chain` | `stockpred chain UNDERLYING` |
| `get_report` | `stockpred report [--symbol X]` |

`--no-log` keeps `get_forecast` from writing the prediction ledger. Calls still
leave the CurieAI host (NETWORK). In `auto` mode they run; in `plan` they are
recorded only.

If `stockpred` is not on PATH, `tools/list` still returns the three names and
`tools/call` returns a structured error string (`isError: true`) instead of
crashing — enough for CI. Force that path with `STOCKPRED_MCP_STUB=1`.

### Security

- Registration is per-user; there is no global catalog.
- Invokes still pass `SandboxPolicyEnforcer` (role, output truncation, audit).
  MCP tools are `NETWORK` + `NETWORK_REQUEST` and do not set `allowed_domains`.
- Write-like MCP names (`create_`, `delete_`, …) still require approval in
  `ask` mode. These three tools are read-named on purpose.
- Prefer loopback or a token-gated host. Header values are stored but never
  returned on the API (`header_keys` only).

---

## Follow-ups (not built)

### curie-fhir

[`curie-fhir`](https://github.com/sreeram843/curie-fhir) turns HL7 v2 / clinical
notes into validated FHIR R4 resources. A future thin MCP server could expose
**read-only** lookup (`get_fhir_resource`, `search_fhir`) against a local HAPI
endpoint — never a write/`$validate` mutate from chat without `ask` approval.
Keep PHI off the CurieAI host: run the MCP wrapper next to curie-fhir, register
a user-owned URL, and treat it as clinical-adjacent (not a product default).
Same JSON-RPC shape as stockpred; do not spawn stdio from the API process.

### curie-prediction-pipeline

[`curie-prediction-pipeline`](https://github.com/sreeram843/curie-prediction-pipeline)
is a streaming deterioration-risk prototype (synthetic data, not for care). A
selective **read-only** MCP tool (`get_risk_score` / `get_alert_status`) could
surface a score for a synthetic encounter id if there is a non-clinical demo
need. Do not federate alert-firing, PHI, or Kafka admin. Governance stays in
that repo; CurieAI would only call a locked-down HTTP MCP URL the user
registers, still wrapped by sandbox_policy.
