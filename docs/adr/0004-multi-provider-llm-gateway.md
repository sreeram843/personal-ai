# 0004 — Multi-provider LLM gateway with per-stage routing

Status: Accepted

## Context

The project needs local (Ollama) and OpenAI-compatible cloud/GPU backends, and the
multi-agent pipeline benefits from routing different workflow stages
(planner/synthesizer/reviewer/writer) to different models.

## Decision

Abstract all inference behind `LLMGateway`, which adapts Ollama and
OpenAI-compatible providers. Route per workflow stage via `LLM_<STAGE>_PROVIDER` /
`LLM_<STAGE>_MODEL` env vars, with `LLM_DEFAULT_PROVIDER` / `LLM_DEFAULT_MODEL` as
fallbacks. The admin portal can override stage→provider/model at runtime without a
redeploy.

## Consequences

- One code path for local and cloud inference; providers are swappable by config.
- Enables low-cost per-stage model selection (small planner/reviewer, large writer).
- Adds adapter-compatibility surface (each provider must speak OpenAI-compatible
  format; native Anthropic is not yet supported).
