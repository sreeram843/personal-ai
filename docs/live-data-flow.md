# Live Data Flow

## Goal

Live queries must return either verified provider data with timestamps or a deterministic guardrail error. They must not degrade into stale or hallucinated generation.

---

## End-to-End Live Data Flow

```mermaid
flowchart TD
    Query([Incoming user query]) --> Intent{is_live_intent_query?}

    Intent -- No --> Pass([Continue to RAG /\nworkflow generation])

    Intent -- Yes --> Cache{AdapterCache hit?}
    Cache -- Hit --> CacheResp[Return cached AdapterResult\ncache_hit=true metric]

    Cache -- Miss --> Resolvers[Try resolvers in order]

    subgraph Resolution Order
        R1[1. FX rate\nFrankfurter API]
        R2[2. Commodity price\nweb search]
        R3[3. Stock price\nweb search]
        R4[4. Weather forecast\nOpen-Meteo]
        R5[5. Current weather\nOpen-Meteo]
        R6[6. News\nDuckDuckGo RSS]
    end

    Resolvers --> R1
    R1 -- match --> Normalize
    R1 -- no match --> R2
    R2 -- match --> Normalize
    R2 -- no match --> R3
    R3 -- match --> Normalize
    R3 -- no match --> R4
    R4 -- match --> Normalize
    R4 -- no match --> R5
    R5 -- match --> Normalize
    R5 -- no match --> R6
    R6 -- match --> Normalize
    R6 -- no match --> Unresolved

    Normalize[Normalize to AdapterResult\ndomain, status, verified,\nsource, fetched_at_utc, ttl_seconds]
    Normalize --> WriteCache[Write to AdapterCache\nwith configured TTL]
    WriteCache --> Render

    Unresolved[No adapter resolved] --> GuardRail[Return LIVE_DATA_NOT_VERIFIED\nguardrail error]

    CacheResp --> Render[Render response string\n+ append Data fetched timestamp]
    Render --> Format([MACHINE_ALPHA_7 formatted\nresponse to client])
    GuardRail --> Format
```

---

## Detection

`LiveDataManager.is_live_intent_query()` marks a prompt as live-intent when it matches one of these domains:

- FX conversion
- commodity pricing
- stock pricing
- current weather
- weather forecast
- news
- other freshness-sensitive prompts detected by the web-search heuristics

---

## Resolution Order

`LiveDataManager.resolve()` checks providers in this order:

1. FX
2. Commodity
3. Stock
4. Weather forecast
5. Current weather
6. News

This order matters because some weather prompts overlap and forecast intent should win before current-weather handling.

---

## Normalized Response Contract

All adapter responses are normalized into `AdapterResult`:

| Field | Description |
|-------|-------------|
| `domain` | Provider category (fx, weather, news, …) |
| `status` | `ok` or `error` |
| `verified` | `true` if provider confirmed the data |
| `source` | Human-readable provider name |
| `provider_timestamp` | Timestamp from the provider |
| `fetched_at_utc` | When this backend fetched the data |
| `ttl_seconds` | Cache TTL for this result |
| `data` | Raw provider payload dict |
| `error_code` | Machine-readable error code if status=error |
| `error_message` | Human-readable error if status=error |

---

## Cache Path

```mermaid
flowchart LR
    Request[Adapter request] --> Key[Build cache key\nadapter:domain:params]
    Key --> Check{Redis or\nMemory cache?}
    Check -- Hit + not expired --> CacheHit([Return cached AdapterResult\nPrometheus: cache_hit=true])
    Check -- Miss or expired --> Provider[Call live provider]
    Provider --> Result[AdapterResult]
    Result --> Store[Store in cache\nwith TTL]
    Store --> Return([Return fresh result\nPrometheus: cache_hit=false])
```

---

## API Guardrails

Both `/chat` and `/rag_chat` follow the same sequence:

```mermaid
flowchart TD
    A[Incoming /chat or /rag_chat] --> B[LiveDataManager.resolve]
    B -- verified result --> C([Return live data response])
    B -- no result, but is_live_intent --> D([Return LIVE_DATA_NOT_VERIFIED])
    B -- no result, not live-intent --> E([Continue to generative pipeline])
```

---

## Rendering Rules

- Successful responses include `Fetched:` timestamps and source names.
- The API layer appends `Data fetched:` markers to enforce provenance in the user-facing payload.
- Error responses keep a deterministic terminal-style format so failure cases are predictable and testable.

---

## Metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `live_adapter_requests_total` | domain, status, source, cache_hit | Total adapter invocations |
| `live_adapter_latency_seconds` | domain, source | Provider call latency histogram |

These metrics are the main signal for cache efficiency, provider failures, and request mix across domains.