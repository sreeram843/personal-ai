# Architecture Decision Records

Decisions are numbered sequentially; numbers are never reused. A superseded ADR
keeps its number and is marked `Superseded`, never deleted.

Each record has four sections: **Status**, **Context**, **Decision**,
**Consequences**.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-persona-via-system-prompt.md) | Persona via system prompt, not fine-tuning | Accepted |
| [0002](0002-live-data-deterministic-short-circuit.md) | Deterministic live-data short-circuit | Accepted |
| [0003](0003-single-governed-assistant.md) | Single governed assistant (no persona switching) | Accepted |
| [0004](0004-multi-provider-llm-gateway.md) | Multi-provider LLM gateway with per-stage routing | Accepted |
| [0005](0005-per-user-tenant-isolation.md) | Per-user tenant isolation | Accepted |
| [0006](0006-compose-profiles-for-runtime-switching.md) | Compose profiles for runtime switching | Accepted |

## Template

```markdown
# NNN — Short title

Status: Accepted | Proposed | Deprecated | Superseded by [NNN](NNN-…)

## Context

Why the decision is needed and the forces at play.

## Decision

What we decided, concretely.

## Consequences

The resulting tradeoffs — what gets easier, what gets harder.
```
