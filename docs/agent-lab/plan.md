# Agent Lab — learning plan

A phased, build-to-learn plan for understanding AI agents by extending this app.
All lab code lives in `app/services/learn_agents/` with routes under `/agent/lab/*`,
isolated from the production chat path.

## Guiding rules

- New code goes in new modules — never touch the production chat path.
- One branch per phase (`learn/phase-1-minimal-agent`, ...), merged when the
  phase's "done when" check passes.
- Every phase ends with a short write-up in `docs/agent-lab/phase-N.md`
  explaining the concept in your own words. That's the real learning artifact.

## Phase 1 — The naked agentic loop (~1 afternoon)

**Goal:** understand what "an agent" is at the wire level: messages array,
tool specs, `tool_calls` response, tool results fed back.

1. Read `app/services/tool_agent.py` end to end; annotate a copy.
2. Build `app/services/learn_agents/minimal_agent.py`: a ~100-line loop with
   one hardcoded tool, calling the LLM endpoint directly via httpx — no
   `ToolRegistry`, no framework.
3. Expose it at `POST /agent/lab/minimal` (`app/api/agent_lab_routes.py`).
4. The endpoint returns the full transcript (every request payload and raw
   response); run 5 prompts and read them.

**Done when:** you can sketch the loop from memory and explain why a max-step
cap exists.

## Phase 2 — Tracing and observability (~1–2 days)

**Goal:** make agent behavior visible; multiplies the value of later phases.

1. Build a `RunTrace` recorder capturing each LLM call (prompt, response,
   latency, tokens) and each tool invocation (args, result, duration).
2. Persist traces (crib the pattern from `app/services/run_store.py`).
3. Add `GET /agent/lab/runs/{id}`; render in the frontend (or plain JSON first).
4. Retrofit the recorder into the Phase 1 agent.

**Done when:** any lab run can be replayed step by step.

## Phase 3 — ReAct research agent (~2–3 days)

**Goal:** planning, acting, observing, and knowing when to stop.

1. Build `research_agent.py` with an explicit Thought → Action → Observation
   scratchpad, using `app/services/web_search.py` as the only tool.
2. Add stopping criteria: max steps, a "final answer" action, token budget.
3. Run the same 5 questions through this agent and `tool_agent.py`; compare
   traces (quality, steps, tokens).
4. Deliberately break it (no step cap, vague goal); document the failure modes.

**Done when:** you can articulate prompted-ReAct vs native tool-calling
tradeoffs with trace evidence.

## Phase 4 — Coding agent (~2–3 days)

**Goal:** the write → run → read-the-error → fix loop. One of the most
illustrative agent patterns because success/failure is unambiguous (code
either runs or it doesn't) — contrast with research, where "good enough" is
fuzzy.

1. Build `coding_agent.py`: given a natural-language spec (and optionally a
   handful of assert-style tests), the agent writes a Python function, runs
   it in a subprocess with a timeout, and feeds the traceback back if it
   fails.
2. Add a static safety check (denylist of dangerous imports/builtins) before
   any generated code is executed — shared with Phase 7's tool-builder.
3. Loop until tests pass or the step cap hits; record every attempt via the
   Phase 2 tracer.
4. Run a handful of small specs (list/dict manipulation, string parsing);
   note how many attempts it typically takes and what kinds of bugs recur.

**Done when:** you can explain why sandboxing generated code matters and
have seen the agent self-correct from at least one real traceback.

## Phase 5 — Multi-agent patterns (~3–4 days)

**Goal:** when do multiple agents beat one, and what does coordination cost?

1. Build a standalone drafter + critic pair (critic scores against a rubric,
   drafter revises once).
2. Run 10 prompts three ways: single agent, drafter+critic, `/workflow_chat`;
   compare quality vs latency/tokens.
3. Re-read `app/services/workflow_roles.py` and the orchestrated runner —
   they should now read as "my two-agent pattern, generalized."

**Done when:** you can say, with traces, where reflection helped and where it
just doubled cost.

## Phase 6 — Memory + evals (~1 week, capstone)

**Goal:** the two things that separate demos from real agent products.

1. Memory-forming agent: extract durable facts after a lab conversation and
   write them via `app/services/user_memory.py`; recall in later sessions.
2. Eval harness: ~15 fixed tasks, a runner for any lab agent, an LLM-as-judge
   scorer, a results table per run.
3. Re-score everything from Phases 1–4; change a prompt, re-run, watch scores.

**Done when:** a prompt change can be *measured* instead of eyeballed.

## Phase 7 (optional) — Tool-building agent

An agent that writes and registers new tools at runtime, reusing the code
safety check from Phase 4 plus `app/services/sandbox_policy.py` and
`app/services/tool_permissions.py` for production-grade gating. Do this only
after Phase 6.

---

Total: roughly 4–5 weeks part-time. End state: a working, measurable agent lab
inside the app plus seven short write-ups.
