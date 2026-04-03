# Architecture

## System Overview

Personal AI is a single-repo local assistant with a FastAPI backend, a Vite/React frontend, deterministic live-data adapters, and an observability stack.

---

## High-Level Component Map

```mermaid
graph TD
    Browser["Browser (React/Vite)"]

    subgraph Backend ["FastAPI Backend"]
        Routes["app/api/routes.py"]
        Orchestrator["OrchestratedChatService"]
        LiveData["LiveDataManager"]
        LLMGateway["LLMGateway"]
        VectorStore["VectorStore (Qdrant)"]
        WebSearch["WebSearchService"]
        AdapterCache["AdapterCache (Redis / Memory)"]
        RunStore["RunStore (memory/runs/)"]
        WorkflowMemory["WorkflowMemoryStore"]
        PersonaManager["PersonaManager"]
    end

    subgraph ExternalServices ["External / Local Services"]
        Ollama["Ollama (LLM + Embeddings)"]
        Qdrant["Qdrant"]
        Redis["Redis (optional)"]
        DuckDuckGo["DuckDuckGo Search"]
        FrankfurterAPI["Frankfurter FX API"]
        WeatherAPI["Open-Meteo Weather API"]
    end

    subgraph Observability
        Prometheus["Prometheus"]
        Grafana["Grafana"]
    end

    Browser -- "POST /chat, /rag_chat, /workflow_chat" --> Routes
    Browser -- "SSE /workflow_chat/stream" --> Routes
    Browser -- "POST /ingest" --> Routes
    Browser -- "GET/POST /personas" --> Routes

    Routes --> LiveData
    Routes --> Orchestrator
    Routes --> RunStore
    Routes --> PersonaManager

    LiveData --> AdapterCache
    LiveData --> WebSearch

    Orchestrator --> LLMGateway
    Orchestrator --> VectorStore
    Orchestrator --> WebSearch
    Orchestrator --> WorkflowMemory

    LLMGateway --> Ollama
    VectorStore --> Qdrant
    AdapterCache --> Redis

    WebSearch --> DuckDuckGo
    WebSearch --> FrankfurterAPI
    WebSearch --> WeatherAPI

    Routes -- "GET /metrics" --> Prometheus
    Prometheus --> Grafana
```

---

## Smart-Mode Routing (POST /smart_chat)

```mermaid
flowchart TD
    Start([User message]) --> Extract[Extract last user message]
    Extract --> LiveCheck{Live-data\nintent?}
    LiveCheck -- Yes, verified --> LiveReturn[Return provider data\nwith timestamp]
    LiveCheck -- Yes, unverified --> GuardrailReturn[Return LIVE_DATA_NOT_VERIFIED\nguardrail error]
    LiveCheck -- No --> SmartMode[_select_smart_mode]
    SmartMode --> Greet{Short greeting\nor ≤4 words?}
    Greet -- Yes --> ChatMode[mode = chat]
    Greet -- No --> Fresh{Fresh web\ndata needed?}
    Fresh -- Yes --> WorkflowMode[mode = workflow]
    Fresh -- No --> Long{Query ≥\n24 words?}
    Long -- Yes --> WorkflowMode
    Long -- No --> Complex{Complex reasoning\nterms present?}
    Complex -- Yes --> WorkflowMode
    Complex -- No --> RAGMode[mode = rag]
    ChatMode --> Orchestrator[OrchestratedChatService]
    RAGMode --> Orchestrator
    WorkflowMode --> Orchestrator
    Orchestrator --> FinalResponse([MACHINE_ALPHA_7 formatted response])
```

---

## Runtime Components

| File | Responsibility |
|------|---------------|
| `app/main.py` | Creates the FastAPI app, applies CORS, serves built frontend from `/app/frontend_dist` |
| `app/api/routes.py` | Owns `/chat`, `/rag_chat`, `/workflow_chat`, `/workflow_chat/stream`, `/workflow_runs*`, `/ingest`, `/metrics`, `/personas*` |
| `app/services/orchestrated_chat.py` | Shared orchestration engine for chat, RAG, and workflow modes |
| `app/services/workflow_roles.py` | Per-agent role instructions: coordinator, retriever, researcher, synthesizer, reviewer, writer |
| `app/services/workflow_memory.py` | File-backed conversation-scoped memory store |
| `app/services/ollama.py` | Async client wrapping Ollama chat and embed endpoints |
| `app/services/llm_gateway.py` | Adapter layer supporting Ollama and OpenAI-compatible backends |
| `app/services/vector_store.py` | Qdrant wrapper for storing and searching embedded chunks |
| `app/services/live_data_manager.py` | Routes live-intent queries through deterministic providers before generative fallback |
| `app/services/web_search.py` | DuckDuckGo search and live data provider integrations (FX, weather, news, stocks) |
| `app/services/adapter_cache.py` | Redis or in-memory TTL cache for normalized adapter responses |
| `app/services/run_store.py` | Durable run records with lifecycle events and checkpoints |
| `app/services/sandbox_policy.py` | Tool-invocation policy enforcement and dangerous-command blocking |
| `app/services/persona_manager.py` | Loads persona files and generates dynamic system prompts |
| `frontend/src/App.tsx` | Top-level UI state, mode switching, uploads, and message history |
| `frontend/src/api.ts` | Browser API client with localhost/remote fallback and Safari retry logic |

---

## Request Paths

### Standard Chat (`POST /chat`)

```mermaid
sequenceDiagram
    participant Browser
    participant Routes as routes.py
    participant LD as LiveDataManager
    participant Orch as OrchestratedChatService
    participant LLM as LLMGateway → Ollama

    Browser->>Routes: POST /chat {messages, conversation_id}
    Routes->>LD: resolve(last_user_message)
    alt Verified live data
        LD-->>Routes: AdapterResult (verified=true)
        Routes-->>Browser: MACHINE_ALPHA_7 response + Data fetched timestamp
    else Live-intent but unverified
        LD-->>Routes: None (is_live_intent=true)
        Routes-->>Browser: LIVE_DATA_NOT_VERIFIED guardrail error
    else Not live-intent
        LD-->>Routes: None
        Routes->>Orch: run_mode(mode="chat")
        Orch->>LLM: generate(messages, system_prompt)
        LLM-->>Orch: raw text
        Orch-->>Routes: ChatResponse
        Routes-->>Browser: MACHINE_ALPHA_7 formatted response
    end
```

---

### Retrieval-Augmented Chat (`POST /rag_chat`)

```mermaid
sequenceDiagram
    participant Browser
    participant Routes as routes.py
    participant LD as LiveDataManager
    participant Orch as OrchestratedChatService
    participant QD as VectorStore (Qdrant)
    participant LLM as LLMGateway → Ollama

    Browser->>Routes: POST /rag_chat {messages}
    Routes->>LD: resolve(last_user_message)
    alt Live-data short-circuit
        LD-->>Routes: AdapterResult or guardrail
        Routes-->>Browser: live data / guardrail response
    else Not live-intent
        Routes->>Orch: run_mode(mode="rag")
        Orch->>Orch: _build_plan → retriever task
        Orch->>QD: search(query_embedding, top_k)
        QD-->>Orch: top-k RetrievedChunk list
        Orch->>LLM: synthesizer(query + retrieval_context)
        LLM-->>Orch: draft
        Orch->>LLM: reviewer(draft)
        LLM-->>Orch: review notes
        Orch->>LLM: writer(draft + review_notes)
        LLM-->>Orch: final answer
        Orch-->>Routes: ChatResponse {message, sources}
        Routes-->>Browser: MACHINE_ALPHA_7 response + sources
    end
```

---

### Multi-Agent Workflow Chat (`POST /workflow_chat`)

```mermaid
flowchart TD
    Start([POST /workflow_chat]) --> LiveGate{Live-data\nguardrail}
    LiveGate -- verified --> LiveResp([Live data response])
    LiveGate -- unverified intent --> GuardResp([LIVE_DATA_NOT_VERIFIED])
    LiveGate -- pass --> Memory[Read WorkflowMemoryStore\nfor conversation_id]
    Memory --> Plan[Coordinator builds\ndependency-aware task graph\nqwen2.5:3b planner]
    Plan --> Budget[Apply token budget policy\ntrim low-priority stages]
    Budget --> Loop{Pending tasks?}
    Loop -- yes --> Ready[Find tasks with resolved deps]
    Ready --> RunTask[Execute task agent]

    RunTask --> Retriever["retriever:\nQdrant vector search\n(internal docs)"]
    RunTask --> Researcher["researcher:\nDuckDuckGo web search\n(fresh context)"]
    RunTask --> Synthesizer["synthesizer:\nBuild draft + evidence markers\n[[evidence:id]]"]
    RunTask --> Reviewer["reviewer (quorum):\nIndependent critique passes"]
    RunTask --> Writer["writer:\nFinal user-facing answer\nllama3:8b"]

    Retriever --> Loop
    Researcher --> Loop
    Synthesizer --> Loop
    Reviewer --> Loop
    Writer --> Loop
    Loop -- done --> WriteMemory[Append to WorkflowMemoryStore]
    WriteMemory --> Respond([ChatResponse\n+ WorkflowTrace + sources])
```

---

### Streaming Workflow Events (`POST /workflow_chat/stream`)

```mermaid
sequenceDiagram
    participant Browser
    participant Routes as routes.py
    participant Orch as OrchestratedChatService
    participant RS as RunStore

    Browser->>Routes: POST /workflow_chat/stream
    Routes->>RS: create_run(mode="workflow") → run_id
    RS-->>Routes: WorkflowRun {status: pending}
    Routes->>Routes: StreamingResponse (text/event-stream)

    loop SSE stream_mode()
        Orch-->>Routes: {type:"workflow", workflow: trace}
        Routes-->>Browser: data: {type:"workflow", steps:[...]}
        Note over Browser: UI updates trace in-place
    end

    Orch-->>Routes: {type:"final", response: ChatResponse}
    Routes->>RS: update_run_status(completed)
    Routes-->>Browser: data: {type:"final", response:{...}}
    Browser->>Browser: Render final answer
```

---

### Workflow Run Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending : create_run()
    pending --> in_progress : workflow starts
    in_progress --> completed : all tasks finish
    in_progress --> failed : unrecoverable error
    in_progress --> paused : operator pause action
    paused --> in_progress : operator resume action
    paused --> cancelled : operator cancel action
    failed --> [*]
    completed --> [*]
    cancelled --> [*]

    note right of in_progress
        Events appended to
        memory/runs/*.events.jsonl
    end note
```

---

### Document Ingestion (`POST /ingest`)

```mermaid
flowchart LR
    Upload([User uploads file\nvia UI]) --> Route[POST /ingest]
    Route --> Chunk[Split text into chunks]
    Chunk --> Embed[Ollama embed\nnomic-embed-text\n768-dim vectors]
    Embed --> Qdrant[VectorStore.upsert\nQdrant collection]
    Qdrant --> Done([Ingest complete\nChunks indexed for RAG])
```

---

### Evidence and Reviewer Quorum

```mermaid
flowchart TD
    Retrieval[Retriever chunks\ntrust_lane=retrieved] --> Evidence[Evidence pool\ntagged by trust lane]
    WebSearch[Web results\ntrust_lane=verified_web] --> Evidence
    Evidence --> Synth[Synthesizer\ncites evidence markers\n[[evidence:id]]]
    Synth --> Check{Evidence markers\npresent?}
    Check -- No markers,\nbut evidence exists --> Warn([Verification warning\ninstead of unsupported claim])
    Check -- Markers present --> Quorum[Reviewer quorum\ndefault 2 independent passes]
    Quorum --> Agg[Aggregate review notes]
    Agg --> Writer[Writer uses\nreviewed draft]
    Writer --> Final([Final answer])
```

---

### Safety and Governance Controls

```mermaid
flowchart TD
    ToolInvoke([Tool invocation request]) --> Policy[SandboxPolicyEnforcer]
    Policy --> RoleCheck{Role in\nallowed_roles?}
    RoleCheck -- No --> Deny([Policy violation error])
    RoleCheck -- Yes --> CmdCheck{Shell command\nin allowlist?}
    CmdCheck -- No --> Deny
    CmdCheck -- Yes --> PathCheck{File path\nallowed?}
    PathCheck -- No --> Deny
    PathCheck -- Yes --> DangerCheck{Dangerous\npatterns?}
    DangerCheck -- Yes --> Deny
    DangerCheck -- No --> Exec([Execute tool])

    HighRisk([High-risk tool]) --> TokenCheck{Scoped capability\ntoken valid?}
    TokenCheck -- No --> Deny
    TokenCheck -- Yes --> Policy
```

---

## Frontend State Model

```mermaid
stateDiagram-v2
    direction LR
    [*] --> ClassicMode : default uiMode=classic
    ClassicMode --> TerminalMode : Toggle UI Mode
    TerminalMode --> ClassicMode : Toggle UI Mode

    state ClassicMode {
        [*] --> SmartConversation : mode=smart (default)
        SmartConversation --> ChatOnly : setMode(chat)
        ChatOnly --> SmartConversation : setMode(smart)
    }

    state "LocalStorage (persisted)" as LS {
        personal_ai_mode
        personal_ai_ui_mode
        personal_ai_persona
        personal_ai_phosphor
        personal_ai_history
        personal_ai_conversation_id
    }
```

**Key localStorage keys:**

| Key | Values | Description |
|-----|--------|-------------|
| `personal-ai-mode` | `smart`, `chat` | Conversation routing mode |
| `personal-ai-ui-mode` | `classic`, `terminal` | UI render mode |
| `personal-ai-persona` | `ideal_chatbot`, `therapist`, `barney` | Active persona |
| `personal-ai-phosphor` | `green`, `amber` | Terminal phosphor color |
| `personal-ai-history` | `ChatMessage[]` | Full chat history |
| `personal-ai-conversation-id` | UUID | Workflow memory key |

---

## Data Stores

```mermaid
graph LR
    App["FastAPI App"]

    subgraph Persistent
        Qdrant["Qdrant\nvector index for document chunks"]
        Redis["Redis (optional)\nadapter response cache"]
        RunFiles["memory/runs/*.json\ndurable run records + event ledger"]
        MemoryFile["memory/workflow_sessions.json\nconversation memory summaries"]
    end

    subgraph ModelServer
        Ollama["Ollama\nLLM inference + embeddings"]
    end

    subgraph Browser
        LocalStorage["localStorage\nUI state + chat history"]
    end

    subgraph Metrics
        Prometheus["Prometheus\ntime-series metrics"]
        Grafana["Grafana\ndashboards"]
    end

    App --> Qdrant
    App --> Redis
    App --> RunFiles
    App --> MemoryFile
    App --> Ollama
    App --> Prometheus
    Prometheus --> Grafana
```

---

## Observability

- `GET /metrics` exposes Prometheus text format.
- `live_adapter_requests_total` — adapter hits labelled by domain, status, source, cache_hit.
- `live_adapter_latency_seconds` — provider latency histogram.
- Prometheus scrapes both itself and the app.
- Grafana is provisioned against the internal `http://prometheus:9090` compose address.

---

## Quality Gate

The repo-level gate is `scripts/quality_gate.sh`. It validates compose config, runs security checks, compiles Python, runs pytest, lints the frontend, builds the frontend, runs Playwright flow and visual tests, and builds the backend image.

---

## Key Constraints

- Live-intent queries must never fall through to unverifiable generation.
- The containerized app serves the frontend from the backend container, so UI changes require rebuilding the app image for compose-based verification.
- Local developer experience supports both direct backend/frontend development and full compose-based stack verification.