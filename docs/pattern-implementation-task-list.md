# Pattern Implementation Task List

This task list converts the identified architecture patterns into deliverable work for this repository.

## Status Legend

- [ ] not started
- [~] in progress
- [x] done

## Track 1: Run Control and Operator Visibility

- [x] Add durable run records for workflow requests.
- [x] Add run-control APIs: create, get, list, pause, resume, cancel.
- [x] Attach `run_id` to workflow response traces.
- [ ] Add frontend run inspector panel for timeline and status.
- [ ] Add pause/resume/cancel controls in frontend workflow UI.

## Track 2: Planning Reliability

- [x] Add dual-phase planner flow (draft planner + verifier planner).
- [ ] Add strict plan rejection codes surfaced in API response.
- [ ] Add planner quality metrics (validity rate, fallback rate).
- [~] Add budget-aware linter checks (step count, fanout, stage limits).

## Track 3: Evidence-First Collaboration

- [x] Require evidence IDs for synthesizer output claims.
- [~] Enforce reviewer checks against evidence references.
- [x] Add critic quorum mode (two lightweight reviewers).
- [ ] Add conflict-resolution pass before final writer stage.

## Track 4: Safety and Governance

- [x] Add per-step capability grants (tool, scope, expiry).
- [x] Add approval gate policy for high-risk actions.
- [ ] Add secret redaction pass for traces/log payloads.
- [x] Add trust-lane tags (`deterministic`, `retrieved`, `verified_web`, `inferred`).

## Track 5: Cost and Performance Controls

- [x] Add run-level token budget and stage budget ceilings.
- [x] Add adaptive retry with error fingerprint classes.
- [ ] Add dynamic concurrency policy by queue depth and latency.
- [ ] Add context compaction and evidence reranking prior to writer stage.

## Track 6: Regression and Replay

- [x] Add event-sourced run ledger for step lifecycle events.
- [ ] Add replay harness for benchmark scenarios.
- [ ] Add golden snapshot assertions for workflow trace and citations.
- [ ] Add CI fail thresholds for planner validity and workflow success rate.

## Current Sprint (Started)

1. Implemented run-control backend endpoints and run trace IDs.
2. Implemented dual-phase planning, reviewer quorum, trust lanes, and evidence marker enforcement.
3. Implemented event ledger, adaptive retry fingerprints, capability grants, and approval gates.
4. Next: wire frontend run inspector and controls to run endpoints.
5. Then: add replay harness and CI quality thresholds.
