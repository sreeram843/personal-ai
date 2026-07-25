# Live Data

Live queries must return **verified provider data with timestamps**, or a deterministic guardrail error. They must not silently fall back to hallucinated generation.

## Intent → adapters

`LiveDataManager` uses `route_live_intent()` to classify domains and slots, then tries resolvers in order:

1. FX rates (Frankfurter → open.er-api.com fallback)
2. Commodity price (web search)
3. Stock price (web search)
4. Weather forecast (Open-Meteo → wttr.in fallback)
5. Current weather (Open-Meteo → wttr.in)
6. News (DuckDuckGo RSS / configured search)

Web evidence is **scored** (not hard-coded to `0.0`) so ranking stays meaningful.

## Cache

- Redis-backed adapter cache when `ENABLE_ADAPTER_CACHE=true`
- TTLs per domain / `ADAPTER_CACHE_DEFAULT_TTL_SECONDS`
- Cache hits emit metrics (`cache_hit`)

## Failure mode

If no adapter resolves verified data → **`LIVE_DATA_NOT_VERIFIED`** (guardrail). Do not invent numbers.

Successful responses append a **Data fetched** timestamp.

## Perplexity / web search

Env `PERPLEXITY_API_KEY` powers web search. Adding Perplexity again under Admin **Providers** is only needed if you want Sonar as a **chat** model.

## Flow diagram

See the mermaid flowchart in-repo: `docs/live-data-flow.md`.

## Related

- [Chat and Routing](Chat-and-Routing)
- [Operations](Operations) — metrics and logs
- [Troubleshooting](Troubleshooting)
