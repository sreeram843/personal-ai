# Phase 5 — Drafter + critic vs `/workflow_chat`

This write-up is from reading the lab pair in `critic_agent.py` against production `workflow_roles.py` and `orchestrated_chat.py`. It is not a live 10-prompt bake-off.

## What the lab pair actually is

`run_critic_agent` is three sequential LLM calls with different system prompts, not three programs. A drafter answers in a few sentences. A critic scores Completeness, Clarity, and Directness out of 10 and lists two to four revision notes. The original drafter then revises once. There are no tools, no retrieval, and no planner. The “agents” differ only in the prompt. That is the smallest multi-agent system that still has a visible coordination cost: two extra round-trips and one extra completion.

The lesson in the module docstring is the right one. The interesting question is whether the extra latency and tokens earned a better answer, not whether the loop is clever.

## What production workflow chat actually is

`POST /workflow_chat` is the same draft → critique → rewrite idea, generalized into a task graph.

`DEFAULT_WORKFLOW_ROLES` names six roles. The coordinator writes a dependency-aware plan (JSON tasks with `depends_on`). Retriever and researcher gather internal docs and public web context. Synthesizer drafts with `[[evidence:id]]` markers. Reviewer returns revision notes only — and by default that is a quorum of two independent critiques. Writer produces the user-facing answer. Production even aliases the lab vocabulary: `_normalize_agent` maps `critic` to `reviewer` and `analyst` to `synthesizer`.

The orchestrator adds machinery the lab never needed: a plan verifier LLM call, a static fallback plan when the coordinator emits invalid JSON, ready-set parallelism (`RUNTIME_MAX_PARALLEL = 8`), per-stage models, token-budget trimming, citation repair, and `WorkflowMemoryStore` for conversation-scoped step summaries. Reviewer notes are not a numeric rubric; they are free-form issues for the writer. Revision is a third role, not the original drafter seeing its own critique.

A typical successful workflow therefore looks like: planner + verifier, optional retrieve/research (tools, not always LLM), synthesizer, two reviewer calls, writer. That is roughly seven to ten model calls plus search, versus the lab’s three.

## Where reflection helped, and where it is just cost

On a short explanation (“what is a race condition?”), a critic pass can catch hedging and missing constraints. That is the lab pair’s sweet spot: one extra look at completeness and directness. It is also where `/workflow_chat` is usually the wrong tool. You still pay for a coordinator, a verifier, empty retrieval, and a quorum review of a draft that did not need sources.

On compare / analyze / multi-hop questions, the production graph is doing a different job than reflection. Retriever and researcher change the *inputs* to the draft. Evidence markers and the writer’s citation guard change whether claims are grounded. Quorum review is cheap insurance against one sleepy critic, at the cost of another full completion. The lab pair cannot do any of that, because it never leaves the chat completion API.

The honest tradeoff, from the code rather than from a new live run:

| Path | Typical LLM calls | Extra vs one-shot | Quality bet | Extra cost is worth it when |
| --- | --- | --- | --- | --- |
| Single lab completion | 1 | 0 | Baseline prose | The question is already self-contained |
| Lab drafter + critic | 3 (draft, critique, revise) | +2 | Clearer, less hedged prose; no new facts | The first draft rambles or ducks the question |
| `/workflow_chat` | ~7–10 (plan, verify, synthesizer, 2× reviewer, writer, plus retrieve/research) | +6–9 | Grounded multi-step answer with a trace | The question needs docs, the web, or citations |

Reflection is a prompt trick. Production workflow is that trick plus a planner and tools. Use the lab pair to learn the trick. Use `/workflow_chat` when the extra calls buy evidence, not when they only buy a second opinion on a paragraph.
