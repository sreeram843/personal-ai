# Phase 6 — Memory-forming agent and eval harness

Phase 6 is the capstone: remember something durable, then measure whether a prompt change moved quality. Both pieces already exist in `app/services/learn_agents/`. This note is what they actually do, why the harness stays opt-in, and how production `/workflow_chat` can reuse the same score table.

## Memory-forming agent

`memory_agent.py` splits memory into two jobs that production chat often conflates.

Extraction is one LLM call. The model reads a transcript and returns a JSON array of short durable facts (preferences, goals, identity, ongoing projects). Transient turns are supposed to be dropped. Parsing is defensive: if the model wraps the array in prose, a regex finds it; bad JSON becomes no facts; the list is capped at ten.

Recall is not another model call. `LabMemoryStore.get_recall_block` turns the last few stored strings into a block meant to be prepended to a later system prompt:

```text
Known about this user:
- Prefers concise answers
- Building a Python CLI tool
```

Storage is a lab-only JSON file (`memory/agent_lab/facts.json`), on purpose. Production already has two other memories: `UserMemoryStore` (rolling user/assistant snippets plus optional facts) and `WorkflowMemoryStore` (per-conversation workflow step summaries). The original lab plan said to write through `user_memory.py`. The code does not, so a lab experiment cannot corrupt real user data. That divergence is correct.

The hard problem this phase is meant to show is still unsolved in the lab: extraction quality. A missed preference never appears in recall. A hallucinated “fact” will. There is no embedding retrieval, no decay, and no merge beyond “append if not already present, keep the last 30.” Recall is a string dump, which is enough to feel the prompt-injection shape of memory and not enough to ship.

## Eval harness (lab agents)

`eval_harness.py` is a fixed task list routed at the lab agents: calculator (minimal), coding (assert tests), research, and one drafter+critic prompt. Scoring is two-track:

- If `expects_substring` is set, the run is a boolean (`passed`). Arithmetic belongs here.
- Otherwise an LLM judge scores 1–5 and a reason sentence. Research and critique belong here.

`summarize()` collapses a list of `EvalResult` into one table: `total`, `deterministic_passed` / `deterministic_total`, `average_judge_score`, `judged_total`. That table is the artifact you compare after changing a prompt. `tests/test_eval_harness.py` only covers uniqueness and that math; it never calls `run_eval_suite()`, because that function always hits a live model.

The bundled set is six tasks, not the ~15 in the original plan. That is enough to exercise each lab agent and not enough to pretend we have a product eval.

## Why the harness must stay opt-in

The judge is a live LLM call. It is slow, billed, and non-deterministic: the same answer can score 4 then 3. CI has no provider, no budget, and no appetite for flake. `run_eval_suite()` also runs the lab agents themselves, which are more live completions (and a subprocess for coding). Putting that on `quality_gate.sh` would couple the merge gate to model availability.

Keep the lab harness behind a manual run. Keep unit tests on pure functions. Treat judge scores as a trend across a prompt change, not as a pass/fail in GitHub Actions.

## Scoring production `/workflow_chat` with the same table

`workflow_eval.py` is the production-shaped sibling. It does not import the lab agents. It runs compare / analyze / multi-hop prompts through `/workflow_chat` (HTTP client), `OrchestratedChatService`, or an injected `async def run_one(prompt) -> str` for tests.

Each task still becomes an `EvalResult` with `agent="workflow"`. Substring checks fill `passed`. Open-ended tasks can use the same lab `_judge` when a live run opts in. `summarize()` is imported unchanged, so a workflow eval and a lab eval print the same keys. After a coordinator or reviewer prompt change, re-run the workflow suite and compare `deterministic_passed` and `average_judge_score` the way Phase 6 already compares lab prompt edits.

Live workflow eval is gated on `RUN_EVAL_WORKFLOW=1` for the same reason as the lab harness: it calls a real model (the workflow graph, and optionally the judge). Default `python -m app.services.learn_agents.workflow_eval` only prints how to turn it on.
