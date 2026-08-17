# 0002 — Deterministic live-data short-circuit

Status: Accepted

## Context

Queries about FX, weather, stocks, news, and nearby places must not be answered by
hallucinated generation. A general LLM path cannot guarantee freshness or truth for
these intents.

## Decision

Route live-intent queries through deterministic providers (`LiveDataManager`) before
any LLM generation. Verified results return provider data with provenance
(`source`, `fetched_at_utc`, `confidence`). Unverifiable live intents fail closed with
a `LIVE_DATA_NOT_VERIFIED` guardrail error rather than falling through to generation.

## Consequences

- Live answers are trustworthy and testable; the failure path is deterministic.
- Adds a hard dependency on provider availability and a normalized adapter/cache
  layer (`AdapterCache`, per-domain TTLs).
- Some edge-case intents require a clarification gate (e.g. nearby places) instead
  of a single provider call.
