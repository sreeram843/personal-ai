# Prometheus Commands and Query Reference

This file is a quick reference for common Prometheus tasks in this project.

## 1) Start and Verify Services

Run from project root.

```bash
docker compose up -d prometheus app
```
Purpose: Starts Prometheus and the FastAPI app (the scrape target).

```bash
docker compose ps
```
Purpose: Confirms containers are running.

```bash
curl -s http://localhost:9090/-/ready
```
Purpose: Checks Prometheus readiness.

```bash
curl -s http://localhost:9090/-/healthy
```
Purpose: Checks Prometheus health.

```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {scrapeUrl: .scrapeUrl, health: .health, lastError: .lastError}'
```
Purpose: Verifies scrape targets are up and shows scrape errors.

## 2) Prometheus UI Basics

Open in browser:

- http://localhost:9090

Useful pages:

- Status -> Targets: scrape health and errors.
- Status -> Configuration: loaded config.
- Graph: run PromQL queries.

## 3) Project Metrics You Already Expose

- live_adapter_requests_total (Counter)
- live_adapter_latency_seconds (Histogram)
- python_gc_objects_collected_total and other runtime metrics

## 4) Core PromQL Queries (Copy/Paste)

### 4.1 Target health

```promql
up
```
Purpose: Shows if each target is up (1) or down (0).

```promql
up{job="personal-ai-app"}
```
Purpose: Checks only your FastAPI app target.

### 4.2 Request volume

```promql
live_adapter_requests_total
```
Purpose: Raw cumulative counter values by labels.

```promql
rate(live_adapter_requests_total[5m])
```
Purpose: Per-second request rate over 5 minutes.

```promql
sum by (domain) (rate(live_adapter_requests_total[5m]))
```
Purpose: Throughput split by live-data domain.

```promql
sum by (domain, status, source, cache_hit) (rate(live_adapter_requests_total[5m]))
```
Purpose: Full breakdown by status/source/cache behavior.

### 4.3 Error monitoring

```promql
sum by (domain) (rate(live_adapter_requests_total{status="error"}[5m]))
```
Purpose: Error request rate by domain.

```promql
sum(rate(live_adapter_requests_total{status="error"}[5m])) / sum(rate(live_adapter_requests_total[5m]))
```
Purpose: Global error ratio (0.0 to 1.0).

### 4.4 Cache effectiveness

```promql
sum(rate(live_adapter_requests_total{cache_hit="true"}[5m]))
```
Purpose: Cache-hit request rate.

```promql
sum(rate(live_adapter_requests_total{cache_hit="true"}[5m])) / sum(rate(live_adapter_requests_total[5m]))
```
Purpose: Cache-hit ratio.

### 4.5 Latency (histogram)

```promql
sum by (le, domain, source) (rate(live_adapter_latency_seconds_bucket[5m]))
```
Purpose: Histogram buckets rate used for percentile calculations.

```promql
histogram_quantile(0.50, sum by (le, domain, source) (rate(live_adapter_latency_seconds_bucket[5m])))
```
Purpose: P50 latency by domain/source.

```promql
histogram_quantile(0.95, sum by (le, domain, source) (rate(live_adapter_latency_seconds_bucket[5m])))
```
Purpose: P95 latency by domain/source.

```promql
histogram_quantile(0.99, sum by (le, domain, source) (rate(live_adapter_latency_seconds_bucket[5m])))
```
Purpose: P99 latency by domain/source.

## 5) Debugging Workflow

If dashboards look empty, run these in order.

```bash
curl -s http://localhost:8000/metrics | head -n 40
```
Purpose: Confirms the app exposes metrics.

```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, scrapeUrl: .scrapeUrl, lastError: .lastError}'
```
Purpose: Confirms Prometheus can scrape your app.

```bash
docker compose logs --tail=120 prometheus app
```
Purpose: Checks scrape and app logs for errors.

```bash
curl -s "http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22personal-ai-app%22%7D"
```
Purpose: API-level check that query execution works.

## 6) Common Gotchas

- Using localhost inside containers:
  - Inside Grafana container, localhost means Grafana itself.
  - Use service DNS names on Docker network, for example http://prometheus:9090.

- No traffic, no metrics movement:
  - Counters/rates need requests to your app.
  - Send a few chat requests, then re-run rate queries.

- Short windows can look noisy:
  - Prefer 5m or 10m windows unless debugging spikes.

## 7) Suggested Starter Alerts (PromQL Conditions)

Use these expressions when you create alert rules.

```promql
up{job="personal-ai-app"} == 0
```
Purpose: App scrape target down.

```promql
(sum(rate(live_adapter_requests_total{status="error"}[5m])) / sum(rate(live_adapter_requests_total[5m]))) > 0.10
```
Purpose: Error ratio above 10%.

```promql
histogram_quantile(0.95, sum by (le) (rate(live_adapter_latency_seconds_bucket[5m]))) > 1.5
```
Purpose: P95 latency over 1.5 seconds.

## 8) Useful Files in This Repo

- monitoring/prometheus.yml
- app/api/routes.py
- docker-compose.yml
