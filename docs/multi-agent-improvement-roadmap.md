# Multi-Agent Improvement Roadmap

## Scope and Safety

This roadmap is based on high-level architecture patterns and observable behavior, not on reusing proprietary leaked implementation code.

## Current Strengths in This Repository

- Shared orchestration backend for chat, rag, and workflow modes.
- Deterministic live-data guardrails before generation.
- Workflow trace streaming over SSE.
- Role-based workflow instructions.
- Conversation-scoped workflow memory persistence.
- Observability baseline with Prometheus metrics.

## Highest-Impact Gaps to Close

### 1. Tooling Runtime and Sandboxing

Why it matters:
A true coding assistant workflow needs controlled tool execution and strict safety boundaries.

Implement:
- Tool registry abstraction with capability metadata and execution policy.
- Sandboxed command runner with allowlist, timeout, and output caps.
- Filesystem policy layer for read/write scopes per workflow role.
- Per-tool audit logs with redaction.

Definition of done:
- Every tool call has policy checks and structured logs.
- Unsafe command classes are blocked deterministically.

### 2. Durable Session and Checkpoint Model

Why it matters:
Long-running workflows need resumability, retries, and post-mortem diagnostics.

Implement:
- Run model: run_id, parent_run_id, state, started_at, completed_at, error.
- Step checkpoint storage with deterministic replay metadata.
- Resume API for interrupted workflow runs.
- Retry policy by error class (transient vs permanent).

Definition of done:
- You can stop and resume a workflow without losing state.
- Failed runs are inspectable and replayable.

### 3. Planner Reliability and Plan Validation

Why it matters:
Planner output quality controls all downstream quality.

Implement:
- Strong planner schema validation with explicit error codes.
- Plan linter: cycle detection, orphan dependency detection, max fanout.
- Confidence scoring and fallback planner templates by mode.
- Dual planner option for high-stakes tasks (draft planner plus verifier planner).

Definition of done:
- Invalid plans never execute.
- Planner quality is observable via metrics.

### 4. Multi-Agent Communication Contract

Why it matters:
Richer collaboration needs more than shared text blocks.

Implement:
- Typed inter-agent messages: context_request, evidence_share, review_feedback, handoff.
- Shared workspace object model with immutable evidence references.
- Agent inbox/outbox persistence per run.

Definition of done:
- Every step can consume structured messages and evidence objects.

### 5. Memory Quality and Consolidation

Why it matters:
Memory grows quickly and can degrade response quality if not curated.

Implement:
- Memory tiers: ephemeral turn memory, conversation memory, durable profile memory.
- Background memory consolidation job:
  - merge duplicates
  - summarize stale entries
  - prune low-value entries
- Memory freshness and confidence tags.

Definition of done:
- Memory size remains bounded.
- Memory retrieval quality improves over time.

### 6. UI and Operator Experience

Why it matters:
As workflows become complex, users need clear control and debuggability.

Implement:
- Run inspector panel with timeline, step status, retries, and tool calls.
- Pause, cancel, resume workflow controls.
- Compact and detailed trace density modes.
- Error drill-down with suggested remediations.

Definition of done:
- User can understand and control a run without logs.

### 7. Evaluation and Regression Harness

Why it matters:
Multi-agent systems regress silently without scenario-based testing.

Implement:
- Workflow benchmark suite:
  - tool-use correctness
  - citation quality
  - latency and cost envelope
  - planner validity rate
- Golden run snapshots for key scenarios.
- CI quality gate with fail thresholds.

Definition of done:
- Every merge is checked against workflow regression scenarios.

### 8. Security and Governance

Why it matters:
A multi-agent runtime increases attack surface.

Implement:
- Secret detection and redaction in prompts, logs, and traces.
- Data classification tags for memory entries and tool outputs.
- Strict outbound network policy by environment.
- Human-approval gates for destructive actions.

Definition of done:
- Sensitive data cannot leak to tools or logs unintentionally.

### 9. Performance and Cost Controls

Why it matters:
Parallel orchestration can spike latency and model cost.

Implement:
- Dynamic concurrency controller by queue depth and model latency.
- Budget-aware planner constraints.
- Context compaction and evidence ranking before synthesis.
- Partial response streaming from writer stage.

Definition of done:
- Predictable run latency and cost ceilings per mode.

### 10. Extensibility Layer

Why it matters:
You will want to add adapters and roles without touching core logic.

Implement:
- Role plugin contract.
- Tool plugin contract.
- Provider adapter interface for local and hosted models.
- Versioned workflow templates.

Definition of done:
- New role or tool integrations can be added with minimal core changes.

## Suggested Execution Plan

### Phase 1 (Immediate)

- Tool registry and sandbox policy.
- Run and step checkpoint model.
- Planner schema hardening and plan linter.
- Run inspector UI basics.

### Phase 2 (Near-term)

- Structured inter-agent messaging.
- Memory consolidation and freshness tagging.
- Regression harness and golden snapshots.
- Pause and resume workflow control.

### Phase 3 (Scale)

- Budget-aware and latency-aware orchestration.
- Plugin interfaces for roles and tools.
- Approval workflows for risky actions.
- Advanced analytics dashboards.

## Measurable Targets

- Planner valid plan rate above 98%.
- Workflow completion success above 95% for benchmark suite.
- Median workflow latency below 8 seconds for standard tasks.
- Tool failure retry recovery above 80% for transient errors.
- Citation accuracy above 95% for rag and workflow modes.

## Recommended Next Implementation Batch

1. Add run_id and step checkpoint persistence schema.
2. Add planner output linter and hard failure before execution.
3. Add tool policy layer with command and path restrictions.
4. Add run inspector panel in the frontend with pause and cancel.
5. Add benchmark scenarios and CI threshold checks.

## Full Delivery Task List

Use this as the execution tracker to complete the full roadmap.

### Epic A - Runtime Safety and Tooling

- [ ] Create `ToolSpec` schema with capability tags and risk class.
- [ ] Add centralized tool registry service with role-based allowlists.
- [ ] Add shell sandbox policy (`allowed_commands`, timeout, output cap, cwd policy).
- [ ] Add filesystem guard (`allowed_read_paths`, `allowed_write_paths`).
- [ ] Add tool-call audit log entries with redaction markers.
- [ ] Add negative tests for blocked commands and blocked paths.

### Epic B - Durable Runs and Checkpoints

- [ ] Add workflow run entities (`run_id`, `mode`, `conversation_id`, `status`, timestamps).
- [ ] Add step checkpoint entities (`step_id`, `state`, `inputs`, `outputs`, `error`).
- [ ] Add run store abstraction (`memory` now, optional Redis/SQLite backend next).
- [ ] Add resume endpoint (`POST /workflow_chat/resume`).
- [ ] Add retry policy metadata by exception category.
- [ ] Add tests for interrupted-run resume and deterministic replay.

### Epic C - Planner Reliability

- [ ] Define strict planner JSON schema (versioned).
- [ ] Add plan linter (cycle detection, orphan edges, max fanout, max depth).
- [ ] Add planner confidence score output.
- [ ] Add hard rejection for invalid plans with explicit error codes.
- [ ] Add fallback static plans by mode.
- [ ] Add planner quality metrics to `/metrics`.

### Epic D - Agent Communication Layer

- [ ] Define typed inter-agent message schema.
- [ ] Add per-run inbox/outbox persistence.
- [ ] Add evidence object model with immutable IDs.
- [ ] Add handoff summaries between synthesizer/reviewer/writer.
- [ ] Add event stream messages for handoff visibility in UI.

### Epic E - Memory Quality and Consolidation

- [ ] Add memory tiering (`ephemeral`, `conversation`, `durable`).
- [ ] Add background consolidation job (merge, summarize, prune).
- [ ] Add freshness/confidence metadata for memory entries.
- [ ] Add memory retrieval ranking by recency and relevance.
- [ ] Add memory compaction tests for large histories.

### Epic F - UI and Operator Controls

- [ ] Add run inspector panel (timeline, step details, retries).
- [ ] Add pause, cancel, and resume controls.
- [ ] Add compact/detailed trace density toggle.
- [ ] Add tool-call detail drawer with input/output snippets.
- [ ] Add error drill-down panel with suggested remediations.

### Epic G - Evaluation and Regression

- [ ] Create benchmark task set (chat, rag, workflow, failure scenarios).
- [ ] Add golden snapshots for deterministic comparison.
- [ ] Add evaluation script for latency/cost/accuracy.
- [ ] Add CI gate thresholds for planner validity and success rate.
- [ ] Add nightly run summary artifact.

### Epic H - Security and Governance

- [ ] Add secret detector in prompts, traces, and logs.
- [ ] Add data classification tags for memory and tool outputs.
- [ ] Add outbound domain/network policy for web-enabled steps.
- [ ] Add approval gate for destructive operations.
- [ ] Add security-focused regression tests.

### Epic I - Performance and Cost

- [ ] Add dynamic concurrency controller.
- [ ] Add token and latency budget limits per run.
- [ ] Add context compaction and evidence reranking.
- [ ] Add adaptive model routing by stage and complexity.
- [ ] Add p50/p95 dashboard panels for each stage.

### Epic J - Extensibility

- [ ] Add role plugin interface.
- [ ] Add tool plugin interface.
- [ ] Add model provider adapter interface.
- [ ] Add versioned workflow template registry.
- [ ] Add example plugin package in `docs/examples`.

## Model Strategy (Low Cost + Faster)

### Current State

Right now the default chat model is `llama3:8b` and embedding model is `nomic-embed-text`.

### Low-Cost Local Models to Consider (Ollama)

Primary candidates:
- `qwen2.5:3b` - very fast, good for planner/reviewer/light synthesis.
- `qwen2.5:7b` - balanced quality/speed for general workflow writing.
- `llama3.2:3b` - low-memory option for lightweight assistant steps.
- `phi3:mini` - compact and fast for structured helper tasks.
- `gemma2:2b` - lowest-cost experimental option.
- `mistral:7b` - strong 7B baseline for higher-quality synthesis.

Embedding alternatives:
- `nomic-embed-text` (keep as default baseline).
- `mxbai-embed-large` (higher quality retrieval, higher cost).
- `snowflake-arctic-embed2` (good retrieval quality tradeoff).

### Recommended Stage-Based Routing

Use different models per workflow stage to reduce cost and latency:

- Coordinator/planner: `qwen2.5:3b`
- Retriever/researcher summarization: `qwen2.5:3b` or `phi3:mini`
- Synthesizer draft: `qwen2.5:7b`
- Reviewer: `qwen2.5:3b`
- Final writer: `mistral:7b` or `llama3:8b`

### Optional Hosted Low-Cost Models

If/when you add cloud fallback:
- OpenAI: `gpt-4o-mini` or `gpt-4.1-mini`
- Anthropic: Haiku-tier model
- Google: Gemini Flash-tier model

Use hosted fallback only for high-complexity or SLA-critical runs.

### Runtime Config Mapping (Current)

| Purpose | Env variable | Example | Notes |
| --- | --- | --- | --- |
| Default provider fallback | `LLM_DEFAULT_PROVIDER` | `ollama` | Used when a stage provider is omitted. |
| Default model fallback | `LLM_DEFAULT_MODEL` | `llama3:8b` | Kept for provider-level defaults. |
| OpenAI-compatible base URL | `LLM_OPENAI_BASE_URL` | `http://localhost:1234` | Enables the `openai` provider adapter when set. |
| OpenAI-compatible API key | `LLM_OPENAI_API_KEY` | `sk-local-or-cloud` | Optional for local gateways, required for hosted APIs. |
| OpenAI-compatible timeout | `LLM_OPENAI_TIMEOUT` | `60.0` | Seconds per request for `openai` provider calls. |
| Planner stage provider | `LLM_PLANNER_PROVIDER` | `ollama` or `openai` | Stage-specific provider routing. |
| Planner stage model | `LLM_PLANNER_MODEL` | `qwen2.5:3b` | Lightweight planner model. |
| Synthesizer stage provider | `LLM_SYNTHESIZER_PROVIDER` | `ollama` or `openai` | Stage-specific provider routing. |
| Synthesizer stage model | `LLM_SYNTHESIZER_MODEL` | `qwen2.5:7b` | Draft synthesis model. |
| Reviewer stage provider | `LLM_REVIEWER_PROVIDER` | `ollama` or `openai` | Stage-specific provider routing. |
| Reviewer stage model | `LLM_REVIEWER_MODEL` | `qwen2.5:3b` | Low-cost reviewer model. |
| Writer stage provider | `LLM_WRITER_PROVIDER` | `ollama` or `openai` | Stage-specific provider routing. |
| Writer stage model | `LLM_WRITER_MODEL` | `llama3:8b` | Final answer model. |

### Practical Rollout Plan for Models

- [ ] Add per-stage model config in settings (`planner_model`, `reviewer_model`, `writer_model`, etc.).
- [ ] Add latency and success metrics by model and by stage.
- [ ] Run A/B benchmark: `llama3:8b` vs `qwen2.5:7b` for writer stage.
- [ ] Set automatic fallback to stronger model only on low confidence or failed review.
- [ ] Re-tune `top_k` and context length per model to avoid over-contexting small models.
