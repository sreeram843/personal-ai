"""Live checks for eggplant: connectivity, indirect injection, workflow smoke."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EGGPLANT_ROOT = Path(__file__).resolve().parents[1]


def _load_security_indirect_cases() -> list[dict[str, Any]]:
    path = EGGPLANT_ROOT / "fixtures" / "security_golden.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    return [
        case
        for case in cases
        if case.get("document_text") and case.get("user_query")
    ]


def _load_workflow_cases(*, limit: int) -> list[dict[str, Any]]:
    path = EGGPLANT_ROOT / "fixtures" / "workflow_golden.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    return [case for case in cases if case.get("expect_orchestrated")][:limit]


def _assert_security_expect(message: str, expect: dict[str, Any]) -> tuple[bool, str | None]:
    if expect.get("must_not_equal") and message.strip() == expect["must_not_equal"]:
        return False, f"Response equals forbidden value: {expect['must_not_equal']!r}"
    for needle in expect.get("must_not_contain") or []:
        if needle in message:
            return False, f"Response contains forbidden substring: {needle!r}"
    return True, None


def check_remote_inference(
    *,
    lm_host: str | None = None,
    ollama_url: str | None = None,
    from_docker: bool = True,
) -> dict[str, Any]:
    """Verify LM Studio and optional Ollama reachability."""
    import httpx

    lm_host = lm_host or os.environ.get("REMOTE_LM_HOST", "192.168.8.245")
    ollama_url = ollama_url or os.environ.get("OLLAMA_CHECK_URL", "http://127.0.0.1:11434")
    lm_url = f"http://{lm_host}:1234/v1/models"

    checks: dict[str, Any] = {"lm_host": lm_host, "checks": {}}

    def _probe(url: str, *, via_docker: bool = False) -> dict[str, Any]:
        if via_docker:
            completed = subprocess.run(
                ["docker", "exec", "personal-ai-app", "curl", "-sS", "-m", "8", url],
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                return {"status": "error", "detail": completed.stderr.strip() or completed.stdout.strip()}
            try:
                body = json.loads(completed.stdout)
            except json.JSONDecodeError:
                body = completed.stdout[:200]
            return {"status": "ok", "body_preview": str(body)[:300]}
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(url)
                response.raise_for_status()
                return {"status": "ok", "body_preview": response.text[:300]}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)}

    checks["checks"]["lm_studio_host"] = _probe(lm_url, via_docker=False)
    if from_docker:
        checks["checks"]["lm_studio_from_app_container"] = _probe(lm_url, via_docker=True)
    checks["checks"]["ollama_host"] = _probe(f"{ollama_url.rstrip('/')}/api/tags", via_docker=False)

    checks["passed"] = all(item.get("status") == "ok" for item in checks["checks"].values())
    return checks


def run_indirect_injection_live(
    *,
    base_url: str,
    timeout_s: float,
    auth_token: str,
) -> dict[str, Any]:
    """Ingest malicious docs, then query via /rag_chat."""
    import httpx

    base = base_url.rstrip("/")
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    cases = _load_security_indirect_cases()
    results: list[dict[str, Any]] = []

    with httpx.Client(timeout=timeout_s, headers=headers) as client:
        for case in cases:
            case_id = str(case["id"])
            doc_path = f"eggplant-security/{case_id}.txt"
            started = time.perf_counter()
            item: dict[str, Any] = {"id": case_id, "source": "security_golden_indirect"}
            try:
                ingest = client.post(
                    f"{base}/ingest",
                    json={
                        "documents": [
                            {
                                "text": case["document_text"],
                                "metadata": {"path": doc_path, "name": doc_path},
                            }
                        ]
                    },
                )
                item["ingest_status"] = ingest.status_code
                if ingest.status_code >= 400:
                    item["passed"] = False
                    item["error"] = ingest.text[:300]
                    results.append(item)
                    continue

                body = ingest.json()
                if body.get("job_id"):
                    job_id = body["job_id"]
                    deadline = time.time() + min(timeout_s, 120.0)
                    while time.time() < deadline:
                        job = client.get(f"{base}/jobs/{job_id}")
                        if job.status_code == 200 and job.json().get("status") in {"completed", "failed"}:
                            if job.json().get("status") == "failed":
                                item["passed"] = False
                                item["error"] = job.json().get("error", "ingest job failed")
                                break
                            break
                        time.sleep(1.0)

                chat = client.post(f"{base}/rag_chat", json={"message": case["user_query"]})
                item["latency_ms"] = int((time.perf_counter() - started) * 1000)
                item["http_status"] = chat.status_code
                if chat.status_code >= 400:
                    item["passed"] = False
                    item["error"] = chat.text[:300]
                else:
                    message = str(chat.json().get("message") or "").strip()
                    item["response_chars"] = len(message)
                    item["response_preview"] = message[:200]
                    ok, reason = _assert_security_expect(message, case.get("expect") or {})
                    item["passed"] = ok and bool(message)
                    if reason:
                        item["error"] = reason
            except Exception as exc:  # noqa: BLE001
                item["passed"] = False
                item["latency_ms"] = int((time.perf_counter() - started) * 1000)
                item["error"] = str(exc)
            results.append(item)

    passed = sum(1 for row in results if row.get("passed"))
    return {
        "status": "completed",
        "endpoint": "/ingest + /rag_chat",
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
    }


def run_workflow_smoke_live(
    *,
    base_url: str,
    limit: int,
    timeout_s: float,
    auth_token: str,
) -> dict[str, Any]:
    """POST /workflow_chat for DeepPlanning-style golden queries."""
    import httpx

    base = base_url.rstrip("/")
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    cases = _load_workflow_cases(limit=limit)
    results: list[dict[str, Any]] = []

    with httpx.Client(timeout=timeout_s, headers=headers) as client:
        for case in cases:
            started = time.perf_counter()
            item: dict[str, Any] = {"id": case["id"], "source": "workflow_golden"}
            try:
                response = client.post(f"{base}/workflow_chat", json={"message": case["query"]})
                item["latency_ms"] = int((time.perf_counter() - started) * 1000)
                item["http_status"] = response.status_code
                if response.status_code >= 400:
                    item["passed"] = False
                    item["error"] = response.text[:300]
                else:
                    message = str(response.json().get("message") or "").strip()
                    item["response_chars"] = len(message)
                    item["passed"] = len(message) >= 40
                    if not item["passed"]:
                        item["error"] = "Response too short for workflow smoke"
            except Exception as exc:  # noqa: BLE001
                item["passed"] = False
                item["latency_ms"] = int((time.perf_counter() - started) * 1000)
                item["error"] = str(exc)
            results.append(item)

    passed = sum(1 for row in results if row.get("passed"))
    latencies = [int(row["latency_ms"]) for row in results if "latency_ms" in row]
    return {
        "status": "completed",
        "endpoint": "/workflow_chat",
        "passed": passed,
        "failed": len(results) - passed,
        "latency_ms_p50": sorted(latencies)[len(latencies) // 2] if latencies else None,
        "cases": results,
    }
