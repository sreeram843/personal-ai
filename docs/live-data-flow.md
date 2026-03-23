# Live Data Flow

## Goal

Live queries must return either verified provider data with timestamps or a deterministic guardrail error. They must not degrade into stale or hallucinated generation.

## Detection

`LiveDataManager.is_live_intent_query()` marks a prompt as live-intent when it matches one of these domains:

- FX conversion
- commodity pricing
- stock pricing
- current weather
- weather forecast
- news
- other freshness-sensitive prompts detected by the web-search heuristics

## Resolution Order

`LiveDataManager.resolve()` checks providers in this order:

1. FX
2. Commodity
3. Stock
4. Weather forecast
5. Current weather
6. News

This order matters because some weather prompts overlap and forecast intent should win before current-weather handling.

## Normalized Response Contract

All adapter responses are normalized into `AdapterResult`:

- `domain`
- `status`
- `verified`
- `source`
- `provider_timestamp`
- `fetched_at_utc`
- `ttl_seconds`
- `data`
- `error_code`
- `error_message`

This lets the API layer render provider-specific messages without branching on raw provider payload shapes.

## Cache Path

1. The manager builds a cache key per domain.
2. `AdapterCache` checks Redis or the in-memory fallback.
3. Cache hits increment Prometheus counters with `cache_hit=true`.
4. Cache misses call the provider and write the normalized result back with the configured TTL.

## API Guardrails

Both `/chat` and `/rag_chat` follow the same sequence:

1. Try deterministic adapter resolution.
2. If verified data exists, render it directly.
3. If the prompt is live-intent and no adapter verified the data, return `LIVE_DATA_NOT_VERIFIED`.
4. Only non-live-intent prompts continue into RAG or base-model generation.

## Rendering Rules

- Successful responses include `Fetched:` timestamps and source names.
- The API layer appends `Data fetched:` markers to enforce provenance in the user-facing payload.
- Error responses keep a deterministic terminal-style format so failure cases are predictable and testable.

## Metrics

- `live_adapter_requests_total`
- `live_adapter_latency_seconds`

These metrics are the main signal for cache efficiency, provider failures, and request mix across domains.