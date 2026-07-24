# Documentation index

Central map for Personal AI / CurAI docs. **Recorded benchmark data** lives in [results/](./results/).

## Getting started

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Project overview, quick start, API summary |
| [compose-profiles.md](./compose-profiles.md) | Docker profiles: local, cloud, remote, gpu-vllm |
| [../docker-setup.md](../docker-setup.md) | Container topology pointer |
| [../frontend/CAPACITOR.md](../frontend/CAPACITOR.md) | iOS/Android native shell |
| [ui-reference.md](./ui-reference.md) | Unified chat UI, settings, latency, live-data cards |
| [cli/README.md](../cli/README.md) | Installable `curai` terminal coding agent |

## Operations & deploy

| Doc | Purpose |
|-----|---------|
| [ops-runbook.md](./ops-runbook.md) | Health checks, prod VM, OAuth, troubleshooting |
| [prod-gcp-vm.md](./prod-gcp-vm.md) | Fresh GCP VM → HTTPS CurAI (DNS, firewall, Caddy, OAuth) |
| [admin-portal.md](./admin-portal.md) | Platform admin (`admin.cura-i.com`): providers, users, usage |
| [deployment-checklist.md](./deployment-checklist.md) | Pre-release checklist |
| [cloud-deploy-aws.md](./cloud-deploy-aws.md) | EKS / Helm |
| [gpu-deployment.md](./gpu-deployment.md) | vLLM on GPU |

## Testing & benchmarks

| Doc | Purpose |
|-----|---------|
| [testing-accuracy.md](./testing-accuracy.md) | Unit/eval layers, accuracy smoke |
| [model-stress-testing.md](./model-stress-testing.md) | **Smoke + stress results**, scripts, interpretation |
| [results/README.md](./results/README.md) | JSON artifact index |

### Quick test commands

```bash
make real-api-smoke          # health, ready, live FX/weather
make model-accuracy-smoke    # LLM + live-data accuracy
make model-stress-local      # concurrent chat load (remote inference)
AUTH_EMAIL=stress-test@example.com make model-stress-prod
./scripts/verify_prod_auth.sh APP_URL=https://app.cura-i.com
```

## Architecture & product

| Doc | Purpose |
|-----|---------|
| [architecture.md](./architecture.md) | Components and data flow |
| [live-data-flow.md](./live-data-flow.md) | FX, weather, stocks adapters |
| [roadmap.md](./roadmap.md) | Phased plan |
| [traits.md](./traits.md) | Assistant governance |
| [multi-agent-improvement-roadmap.md](./multi-agent-improvement-roadmap.md) | Workflow + model strategy |

## Integrations

| Doc | Purpose |
|-----|---------|
| [mcp-servers.md](./mcp-servers.md) | Cursor IDE MCP |
| [penpot-mcp.md](./penpot-mcp.md) | Penpot design MCP |

## Current environments (2026-06-22)

| Environment | URL / access | Chat model | Config |
|-------------|--------------|------------|--------|
| **Local remote** | `http://localhost:8000` | `qwen-3-14b-instruct` via LM Studio @ `192.168.10.1:1234` | `.env.remote`, `make up-remote` |
| **Production** | `https://app.cura-i.com` | Cloud (Groq/etc. per `.env.cloud`) | VM + `make deploy-prod` |
| **iOS Simulator** | Capacitor WebView → `localhost:8000` | Same as local API | `frontend/CAPACITOR.md` |

See [model-stress-testing.md](./model-stress-testing.md) for latency benchmarks on both environments.
