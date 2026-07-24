# Ops runbook

Restart the cache service before reindexing search. Confirm redis PING returns PONG.
After cache restart, trigger a background reindex job and watch `/jobs/{id}` until success.
