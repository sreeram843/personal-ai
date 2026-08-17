# Documentation index

Map of everything under `docs/`. Recorded benchmark data lives in [results/](./results/).

## Reference

| Doc | Purpose |
|-----|---------|
| [architecture.md](./architecture.md) | System design, components, data flow, key constraints |
| [api.md](./api.md) | HTTP + OpenAI-compatible API surface |
| [traits.md](./traits.md) | Assistant governance (seven traits) |
| [live-data-flow.md](./live-data-flow.md) | Live adapters, cache, and guardrails |
| [compose-profiles.md](./compose-profiles.md) | Docker Compose runtime profiles |
| [ui-reference.md](./ui-reference.md) | Chat UI layout and mobile behavior |

## Decisions

| Doc | Purpose |
|-----|---------|
| [adr/](./adr/) | Architecture Decision Records (one file per decision) |

## Operations & deploy (runbooks)

| Doc | Purpose |
|-----|---------|
| [runbooks/ops-runbook.md](./runbooks/ops-runbook.md) | Health checks, prod VM, OAuth, backups, troubleshooting |
| [runbooks/prod-gcp-vm.md](./runbooks/prod-gcp-vm.md) | Fresh GCP VM → HTTPS CurAI (DNS, firewall, Caddy, OAuth) |
| [runbooks/cloud-deploy-aws.md](./runbooks/cloud-deploy-aws.md) | EKS + RDS + Redis + Helm |
| [runbooks/gpu-deployment.md](./runbooks/gpu-deployment.md) | vLLM on GPU |
| [runbooks/monitoring-subdomain.md](./runbooks/monitoring-subdomain.md) | Grafana HTTPS subdomain |
| [runbooks/deployment-checklist.md](./runbooks/deployment-checklist.md) | Pre-release checklist |
| [runbooks/prod-smoke.md](./runbooks/prod-smoke.md) | Scheduled/manual production health, auth, and chat smoke |
| [admin-portal.md](./admin-portal.md) | Platform admin (`admin.cura-i.com`): providers, users, usage |
| [marketing-site.md](./marketing-site.md) | Marketing/legal domain split and Squarespace copy |

## Testing & benchmarks

| Doc | Purpose |
|-----|---------|
| [testing-accuracy.md](./testing-accuracy.md) | Unit/eval layers, routing golden set, accuracy smoke |
| [model-stress-testing.md](./model-stress-testing.md) | Smoke + stress methodology and results |
| [eggplant-eval.md](./eggplant-eval.md) | Eggplant dataset evaluation summary |
| [hf-dataset-selection.md](./hf-dataset-selection.md) | Which public datasets help this chatbot |
| [results/](./results/) | JSON result artifacts |

## Product & planning

| Doc | Purpose |
|-----|---------|
| [roadmap.md](./roadmap.md) | Phased plan (0–3 complete) |
| [portfolio-embed.md](./portfolio-embed.md) | Embeddable demo preview |
| [agent-lab/plan.md](./agent-lab/plan.md) | Phased build-to-learn agent lab |

## Integrations

| Doc | Purpose |
|-----|---------|
| [mcp-servers.md](./mcp-servers.md) | IDE MCP setup (Cursor) |
| [penpot-mcp.md](./penpot-mcp.md) | Penpot design MCP |

## Quick commands

```bash
make real-api-smoke          # health, ready, live FX/weather
make model-accuracy-smoke    # LLM + live-data accuracy
make model-stress-local      # concurrent chat load (remote inference)
AUTH_EMAIL=stress-test@example.com make model-stress-prod
./scripts/verify_prod_auth.sh APP_URL=https://app.cura-i.com
```
