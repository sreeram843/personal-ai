# 0003 — Single governed assistant (no persona switching)

Status: Accepted

## Context

The system originally supported multiple switchable personas (each a full prompt
package, plus `GET /personas`, `POST /personas/switch`, etc.). This multiplied
surface area and governance burden for a product whose value is one reliable
assistant.

## Decision

Remove the persona system entirely. Ship a single assistant governed by the seven
traits in `docs/traits.md`, rendered by `app/prompts/system.md`.

## Consequences

- One prompt to govern, test, and maintain; simpler product.
- Persona-related endpoints and their tests were removed.
- Tradeoff: no user-facing personality switching; customization is limited to the
  single governed persona.
