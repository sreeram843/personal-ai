# 0005 — Per-user tenant isolation

Status: Accepted

## Context

Multi-user support requires that no user can read another user's conversations,
documents, or workflow runs.

## Decision

Scope all persistent state by `user_id`: conversations/messages in Postgres,
document chunks in Qdrant via a `user_id` payload filter on every upsert/search,
and workflow memory / run stores via per-user namespaces (disk paths or Redis).

## Consequences

- Tenant isolation is enforced at the storage layer, not just in API code.
- Every ingest/search/run path must carry and validate `user_id` — verified by
  property-style isolation tests (`test_eval_tenant_isolation.py`).
- Slightly more complex store APIs; isolation is a correctness invariant, not an
  optimization.
