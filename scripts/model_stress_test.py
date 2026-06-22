#!/usr/bin/env python3
"""Concurrent stress test for POST /chat (local Mac Mini or production).

Usage:
  # Local remote inference (default)
  python3 scripts/model_stress_test.py --profile local

  # Production (requires auth — see docs/model-stress-testing.md)
  BASE_URL=https://app.cura-i.com AUTH_TOKEN=... python3 scripts/model_stress_test.py --profile prod

  # Save machine-readable results
  python3 scripts/model_stress_test.py --profile local --output docs/results/stress-local.json

Run inside Docker when httpx is missing on the host:
  docker compose exec -T app python3 - < scripts/model_stress_test.py --profile local
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RequestResult:
    index: int
    ok: bool
    http_status: int
    wall_ms: float
    server_latency_ms: float | None
    message_chars: int
    error: str


@dataclass
class StressReport:
    label: str
    base_url: str
    profile: str
    started_at: str
    requests: int
    concurrency: int
    timeout_s: float
    warmup: bool
    per_request: list[RequestResult] = field(default_factory=list)
    total_wall_s: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)


PROMPTS = [
    "What is 17+25? Reply with only the number.",
    "Name one planet. One word only.",
    "What color is the sky? One word.",
    "Capital of France? One word.",
    "How many days in a week? Reply with a number.",
    "Is water wet? Yes or no only.",
    "2 times 6 equals? Number only.",
    "First month of the year? One word.",
]

PROFILE_DEFAULTS = {
    "local": {"requests": 8, "concurrency": 4, "timeout": 180.0},
    "prod": {"requests": 4, "concurrency": 2, "timeout": 120.0},
}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def build_summary(results: list[RequestResult], total_wall_s: float) -> dict[str, Any]:
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    wall = [r.wall_ms for r in ok]
    server = [r.server_latency_ms for r in ok if r.server_latency_ms is not None]
    summary: dict[str, Any] = {
        "total_requests": len(results),
        "succeeded": len(ok),
        "failed": len(failed),
        "total_wall_s": round(total_wall_s, 2),
        "throughput_req_per_s": round(len(ok) / total_wall_s, 3) if ok and total_wall_s > 0 else 0,
    }
    if wall:
        summary["wall_latency_ms"] = {
            "min": round(min(wall)),
            "p50": round(percentile(wall, 50)),
            "p95": round(percentile(wall, 95)),
            "max": round(max(wall)),
        }
    if server:
        summary["server_latency_ms"] = {
            "min": round(min(server)),
            "p50": round(percentile(server, 50)),
            "p95": round(percentile(server, 95)),
            "max": round(max(server)),
        }
        if wall and len(server) == len(wall):
            overhead = [w - s for w, s in zip(wall, server)]
            summary["overhead_wall_minus_server_ms"] = {"p50": round(percentile(overhead, 50))}
    if failed:
        summary["failures"] = [{"index": r.index, "error": r.error or str(r.http_status)} for r in failed]
    return summary


async def resolve_auth_headers(client, base_url: str) -> dict[str, str]:
    token = (os.environ.get("AUTH_TOKEN") or "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}

    email = (os.environ.get("AUTH_EMAIL") or "").strip()
    body: dict[str, str] = {}
    if email:
        body["email"] = email

    response = await client.post(f"{base_url.rstrip('/')}/auth/token", json=body, timeout=20.0)
    if response.status_code >= 400:
        detail = response.text[:200]
        raise RuntimeError(
            f"Could not obtain auth token (HTTP {response.status_code}): {detail}. "
            "Set AUTH_TOKEN or AUTH_EMAIL — see docs/model-stress-testing.md"
        )
    payload = response.json()
    token = str(payload.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Auth token response missing access_token")
    return {"Authorization": f"Bearer {token}"}


async def post_chat(
    client,
    base_url: str,
    prompt: str,
    timeout: float,
    headers: dict[str, str],
) -> tuple[int, dict, float]:
    started = time.perf_counter()
    response = await client.post(
        f"{base_url.rstrip('/')}/chat",
        json={"message": prompt},
        headers=headers,
        timeout=timeout,
    )
    wall_ms = (time.perf_counter() - started) * 1000
    payload: dict = {}
    try:
        payload = response.json()
    except Exception:
        payload = {"message": response.text[:200], "detail": response.text[:200]}
    return response.status_code, payload, wall_ms


async def run_one(
    semaphore: asyncio.Semaphore,
    client,
    base_url: str,
    headers: dict[str, str],
    index: int,
    prompt: str,
    timeout: float,
) -> RequestResult:
    async with semaphore:
        try:
            status, body, wall_ms = await post_chat(client, base_url, prompt, timeout, headers)
            message = str(body.get("message", ""))
            if not message and body.get("detail"):
                message = str(body.get("detail", ""))
            server_ms = body.get("latency_ms")
            server_latency = float(server_ms) if isinstance(server_ms, (int, float)) else None
            ok = status == 200 and len(message.strip()) > 0
            error = "" if ok else f"HTTP {status}: {message[:120] or 'empty body'}"
            return RequestResult(
                index=index,
                ok=ok,
                http_status=status,
                wall_ms=wall_ms,
                server_latency_ms=server_latency,
                message_chars=len(message),
                error=error,
            )
        except Exception as exc:
            return RequestResult(
                index=index,
                ok=False,
                http_status=0,
                wall_ms=0.0,
                server_latency_ms=None,
                message_chars=0,
                error=str(exc)[:200],
            )


def print_summary(results: list[RequestResult], total_wall_s: float) -> int:
    summary = build_summary(results, total_wall_s)
    print("\n=== Stress test summary ===")
    print(f"  Total requests : {summary['total_requests']}")
    print(f"  Succeeded      : {summary['succeeded']}")
    print(f"  Failed         : {summary['failed']}")
    print(f"  Wall time      : {summary['total_wall_s']}s")
    print(f"  Throughput     : {summary['throughput_req_per_s']} req/s")
    if "wall_latency_ms" in summary:
        w = summary["wall_latency_ms"]
        print(f"  Wall latency   : min {w['min']}ms | p50 {w['p50']}ms | p95 {w['p95']}ms | max {w['max']}ms")
    if "server_latency_ms" in summary:
        s = summary["server_latency_ms"]
        print(f"  Server latency : min {s['min']}ms | p50 {s['p50']}ms | p95 {s['p95']}ms | max {s['max']}ms")
    if "overhead_wall_minus_server_ms" in summary:
        print(f"  Overhead p50   : {summary['overhead_wall_minus_server_ms']['p50']}ms")
    for failure in summary.get("failures", []):
        print(f"  Failure #{failure['index']}: {failure['error']}")
    return 0 if summary["failed"] == 0 else 1


async def main() -> int:
    parser = argparse.ArgumentParser(description="Stress test POST /chat")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--profile", choices=["local", "prod", "custom"], default="custom")
    parser.add_argument("--requests", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--warmup", action="store_true", default=True)
    parser.add_argument("--no-warmup", action="store_false", dest="warmup")
    parser.add_argument("--label", default="")
    parser.add_argument("--output", default="", help="Write JSON report to this path")
    args = parser.parse_args()

    if args.profile != "custom":
        defaults = PROFILE_DEFAULTS[args.profile]
        if args.profile == "prod" and not os.environ.get("BASE_URL"):
            args.base_url = "https://app.cura-i.com"
        requests = args.requests if args.requests is not None else defaults["requests"]
        concurrency = args.concurrency if args.concurrency is not None else defaults["concurrency"]
        timeout = args.timeout if args.timeout is not None else defaults["timeout"]
    else:
        requests = args.requests if args.requests is not None else 8
        concurrency = args.concurrency if args.concurrency is not None else 4
        timeout = args.timeout if args.timeout is not None else 180.0

    label = args.label or f"{args.profile}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    try:
        import httpx
    except ImportError:
        print("httpx is required. Run via docker compose exec -T app python3 -", file=sys.stderr)
        return 2

    print("=== Model stress test ===")
    print(f"  Label      : {label}")
    print(f"  Profile    : {args.profile}")
    print(f"  Target     : {args.base_url.rstrip('/')}/chat")
    print(f"  Requests   : {requests}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Timeout    : {timeout}s")

    started_at = datetime.now(timezone.utc).isoformat()
    report = StressReport(
        label=label,
        base_url=args.base_url.rstrip("/"),
        profile=args.profile,
        started_at=started_at,
        requests=requests,
        concurrency=concurrency,
        timeout_s=timeout,
        warmup=args.warmup,
    )

    async with httpx.AsyncClient() as client:
        health = await client.get(f"{args.base_url.rstrip('/')}/health", timeout=15.0)
        health.raise_for_status()
        print(f"  Health       : {health.json().get('status', 'ok')}")

        ready = await client.get(f"{args.base_url.rstrip('/')}/ready", timeout=15.0)
        ready.raise_for_status()
        ready_body = ready.json()
        if ready_body.get("status") != "ready":
            print(f"Stack not ready: {json.dumps(ready_body)[:300]}", file=sys.stderr)
            return 2
        print("  Ready        : ok")

        headers = await resolve_auth_headers(client, args.base_url)
        print("  Auth         : ok")

        if args.warmup:
            print("  Warmup       : sending 1 request...")
            status, body, wall = await post_chat(
                client,
                args.base_url,
                "Reply with exactly: warmup ok",
                timeout,
                headers,
            )
            if status != 200 or not str(body.get("message", "")).strip():
                print(f"Warmup failed: HTTP {status} {str(body)[:200]}", file=sys.stderr)
                return 2
            print(f"  Warmup done  : {wall:.0f}ms (server latency_ms={body.get('latency_ms')})")

        semaphore = asyncio.Semaphore(max(1, concurrency))
        batch_started = time.perf_counter()
        tasks = [
            run_one(
                semaphore,
                client,
                args.base_url,
                headers,
                i + 1,
                PROMPTS[i % len(PROMPTS)],
                timeout,
            )
            for i in range(requests)
        ]
        results = await asyncio.gather(*tasks)
        report.total_wall_s = time.perf_counter() - batch_started
        report.per_request = list(results)
        report.summary = build_summary(results, report.total_wall_s)

    for r in sorted(results, key=lambda x: x.index):
        status = "ok" if r.ok else "FAIL"
        server = f"{r.server_latency_ms:.0f}ms" if r.server_latency_ms is not None else "n/a"
        print(f"  #{r.index:02d} {status:4s} wall={r.wall_ms:7.0f}ms server={server:>8s} chars={r.message_chars}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        payload = {
            **asdict(report),
            "per_request": [asdict(r) for r in report.per_request],
        }
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\n  Wrote report : {args.output}")

    return print_summary(results, report.total_wall_s)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
