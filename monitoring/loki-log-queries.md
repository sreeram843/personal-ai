# Loki Log Search Reference

Grafana Explore → select **loki** datasource, or open the **Service Logs** dashboard (one panel per container).

## Per-service queries

```logql
{container="personal-ai-app"}
{container="personal-ai-postgres"}
{container="personal-ai-redis"}
{container="personal-ai-qdrant"}
{container="personal-ai-worker"}
{container="personal-ai-prometheus"}
```

## Filter for errors (any service)

```logql
{container="personal-ai-app"} |~ "(?i)error|exception|traceback|failed"
{container="personal-ai-postgres"} |~ "(?i)error|fatal"
```

## Verify Loki is receiving logs

```bash
curl -s http://localhost:3100/ready
curl -s 'http://localhost:3100/loki/api/v1/labels'
```

## If logs are empty

1. Confirm Promtail is running: `docker compose ps promtail`
2. Check Promtail logs: `docker compose logs promtail`
3. Generate traffic (send a chat message) and refresh Grafana
4. Promtail only ships containers named `personal-ai-*`
