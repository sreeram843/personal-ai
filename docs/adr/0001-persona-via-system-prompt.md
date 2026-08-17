# 0001 — Persona via system prompt, not fine-tuning

Status: Accepted

## Context

The assistant needed a consistent, governable personality. The alternative was
fine-tuning a separate model per persona (the "BarneyBot" approach): one model
per character, expensive to train, slow to switch, and opaque.

## Decision

Define behavior as a curated system prompt (the seven traits in
`docs/traits.md`, rendered by `app/prompts/system.md`) injected into a single base
model. No per-persona fine-tuning.

## Consequences

- New behavior is a text edit, not a training run — hours, not weeks.
- Transparent and auditable: read the traits, understand the behavior.
- Switches instantly; no model reload.
- Costs prompt tokens per request and relies on careful prompt engineering rather
  than "deep" weight-level encoding.
