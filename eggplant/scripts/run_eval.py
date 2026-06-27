#!/usr/bin/env python3
"""Run offline eggplant verification against downloaded datasets and in-repo golden sets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EGGPLANT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = EGGPLANT_ROOT / "manifest.json"
DATASETS_DIR = EGGPLANT_ROOT / "datasets"
RESULTS_DIR = EGGPLANT_ROOT / "results"
DOCS_RESULTS_DIR = REPO_ROOT / "docs" / "results"

INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer mode",
    "you are dan",
    "do anything now",
    "jailbreak",
    "disregard",
    "override",
    "new instructions",
)


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_dataset_file(entry_id: str) -> dict[str, Any] | None:
    path = DATASETS_DIR / f"{entry_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _row_text(row: dict[str, Any]) -> str:
    for key in ("text", "prompt", "query", "question", "input", "content", "instruction"):
        value = row.get(key)
        if isinstance(value, str):
            return value
    return ""


def _row_label(row: dict[str, Any]) -> Any:
    for key in ("label", "labels", "is_injection", "injection", "class", "category"):
        if key in row:
            return row[key]
    return None


def _looks_like_injection(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in INJECTION_MARKERS)


def _run_pytest(test_paths: list[str]) -> dict[str, Any]:
    python = REPO_ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)
    cmd = [
        str(python),
        "-m",
        "pytest",
        *test_paths,
        "-q",
        "--no-cov",
    ]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    return {
        "command": " ".join(cmd),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-2000:],
        "passed": completed.returncode == 0,
    }


def _probe_injection_labels(entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") or []
    labeled = 0
    positives = 0
    heuristic_hits_on_labeled_positive = 0
    false_heuristic_on_labeled_negative = 0

    for row in rows:
        text = _row_text(row)
        if not text:
            continue
        label = _row_label(row)
        if label is None:
            continue
        labeled += 1
        label_str = str(label).lower()
        is_positive = label_str in {"1", "true", "injection", "jailbreak", "malicious", "attack"}
        if label in (1, True):
            is_positive = True
        if label in (0, False):
            is_positive = False
        if label in (2, "2"):
            is_positive = True

        heuristic = _looks_like_injection(text)
        if is_positive:
            positives += 1
            if heuristic:
                heuristic_hits_on_labeled_positive += 1
        elif heuristic:
            false_heuristic_on_labeled_negative += 1

    recall = (
        heuristic_hits_on_labeled_positive / positives if positives else None
    )
    return {
        "entry_id": entry_id,
        "rows": len(rows),
        "labeled_rows": labeled,
        "positive_labels": positives,
        "heuristic_recall_on_positives": recall,
        "heuristic_false_positive_on_negatives": false_heuristic_on_labeled_negative,
        "note": "Heuristic only — not a production guardrail score.",
    }


def _probe_injection_heuristic(entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") or []
    hits = sum(1 for row in rows if _looks_like_injection(_row_text(row)))
    return {
        "entry_id": entry_id,
        "rows": len(rows),
        "heuristic_injection_hits": hits,
        "heuristic_hit_rate": (hits / len(rows)) if rows else None,
    }


def _probe_bfcl(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") or []
    question_keys = {"question", "prompt", "input"}
    tool_keys = {"tools", "function", "functions", "tool_list"}
    with_questions = sum(1 for row in rows if any(key in row for key in question_keys))
    with_tools = sum(1 for row in rows if any(key in row for key in tool_keys))
    return {
        "rows": len(rows),
        "rows_with_question_like_field": with_questions,
        "rows_with_tool_schema_field": with_tools,
        "mappable_to_builtin_tools": False,
        "note": "BFCL tool schemas differ; use as pattern reference only.",
    }


def _security_golden_heuristics() -> dict[str, Any]:
    from app.services.information_routing import is_quick_social_utterance, is_trivial_chitchat

    path = EGGPLANT_ROOT / "fixtures" / "security_golden.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for case in cases:
        prompt = case.get("prompt") or case.get("user_query") or ""
        expect = case.get("expect") or {}
        checks: dict[str, Any] = {"id": case["id"], "attack_type": case.get("attack_type")}
        if expect.get("routing_not_trivial"):
            checks["not_trivial_chitchat"] = not is_trivial_chitchat(prompt)
            checks["not_quick_social"] = not is_quick_social_utterance(prompt)
        results.append(checks)
    passed = all(
        all(value is True for key, value in item.items() if key not in {"id", "attack_type"})
        for item in results
    )
    return {"passed": passed, "cases": results}


def _routing_golden_pytest() -> dict[str, Any]:
    return _run_pytest(["tests/test_eval_routing_accuracy.py"])


def _tenant_isolation_pytest() -> dict[str, Any]:
    return _run_pytest(["tests/test_eval_tenant_isolation.py"])


def _collect_live_prompt_cases(*, limit: int) -> list[dict[str, str]]:
    """Build a small live-smoke set: internal goldens first, then injection samples."""
    cases: list[dict[str, str]] = []

    security_path = EGGPLANT_ROOT / "fixtures" / "security_golden.json"
    if security_path.is_file():
        for item in json.loads(security_path.read_text(encoding="utf-8")):
            if item.get("document_text"):
                continue  # indirect cases use run_indirect_injection_live
            prompt = str(item.get("prompt") or "").strip()
            if prompt:
                cases.append({"id": str(item.get("id") or "security"), "source": "security_golden", "prompt": prompt})

    routing_path = REPO_ROOT / "tests" / "fixtures" / "routing_golden.json"
    if routing_path.is_file():
        for item in json.loads(routing_path.read_text(encoding="utf-8")):
            prompt = str(item.get("query") or "").strip()
            if prompt:
                cases.append({"id": f"routing-{len(cases)}", "source": "routing_golden", "prompt": prompt})

    injection_path = DATASETS_DIR / "hl-jayavibhav-safety.json"
    if injection_path.is_file():
        rows = json.loads(injection_path.read_text(encoding="utf-8")).get("rows") or []
        for row in rows:
            if len(cases) >= limit:
                break
            text = _row_text(row)
            if not text:
                continue
            label = str(_row_label(row))
            cases.append(
                {
                    "id": f"hl-safety-{label}-{len(cases)}",
                    "source": "hl-jayavibhav-safety",
                    "prompt": text[:2000],
                    "label": label,
                }
            )

    return cases[:limit]


def _run_live_llm_smoke(
    *,
    base_url: str,
    limit: int,
    timeout_s: float,
    auth_token: str,
) -> dict[str, Any]:
    """POST /chat against a running Personal AI stack (e.g. LM Studio via make up-remote)."""
    import httpx

    base = base_url.rstrip("/")
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    cases = _collect_live_prompt_cases(limit=limit)
    if not cases:
        return {"status": "failed", "error": "No live prompt cases found.", "cases": []}

    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=timeout_s, headers=headers) as client:
            ready = client.get(f"{base}/ready")
            if ready.status_code != 200:
                return {
                    "status": "failed",
                    "error": f"GET /ready returned HTTP {ready.status_code}",
                    "cases": [],
                }
            ready_body = ready.json()
            is_ready = ready_body.get("status") == "ready" or ready_body.get("ready") is True
            if not is_ready:
                return {
                    "status": "failed",
                    "error": f"App not ready: {ready_body}",
                    "cases": [],
                }

            for case in cases:
                started = time.perf_counter()
                item: dict[str, Any] = {
                    "id": case["id"],
                    "source": case["source"],
                    "prompt_chars": len(case["prompt"]),
                }
                if case.get("label") is not None:
                    item["label"] = case["label"]
                try:
                    response = client.post(f"{base}/chat", json={"message": case["prompt"]})
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    item["latency_ms"] = elapsed_ms
                    item["http_status"] = response.status_code
                    if response.status_code >= 400:
                        item["passed"] = False
                        item["error"] = response.text[:300]
                    else:
                        body = response.json()
                        message = str(body.get("message") or "").strip()
                        item["response_chars"] = len(message)
                        item["passed"] = bool(message) and not message.startswith("ERROR")
                except Exception as exc:  # noqa: BLE001
                    item["passed"] = False
                    item["latency_ms"] = int((time.perf_counter() - started) * 1000)
                    item["error"] = str(exc)
                results.append(item)
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error": str(exc), "cases": results}

    passed = sum(1 for row in results if row.get("passed"))
    latencies = [int(row["latency_ms"]) for row in results if "latency_ms" in row]
    return {
        "status": "completed",
        "backend_note": (
            "Calls POST /chat on the running app. With make up-remote, chat uses LM Studio "
            "(LLM_OPENAI_BASE_URL in .env.remote); embeddings stay on Ollama."
        ),
        "base_url": base,
        "case_limit": limit,
        "passed": passed,
        "failed": len(results) - passed,
        "latency_ms_p50": sorted(latencies)[len(latencies) // 2] if latencies else None,
        "cases": results,
    }


def _retrieval_golden_pytest() -> dict[str, Any]:
    return _run_pytest(["tests/test_eval_retrieval_accuracy.py"])


def _tool_routing_pytest() -> dict[str, Any]:
    return _run_pytest(["tests/test_eval_tool_routing.py"])


def _workflow_routing_pytest() -> dict[str, Any]:
    return _run_pytest(["tests/test_eval_workflow_routing.py"])


def _build_report(
    *,
    include_live: bool,
    include_indirect: bool,
    include_workflow: bool,
    include_connectivity: bool,
    base_url: str,
    live_limit: int,
    live_timeout_s: float,
    auth_token: str,
) -> dict[str, Any]:
    manifest = _load_manifest()
    download_status_path = DATASETS_DIR / "download_status.json"
    download_status = None
    if download_status_path.exists():
        download_status = json.loads(download_status_path.read_text(encoding="utf-8"))

    dataset_probes: list[dict[str, Any]] = []
    for entry in manifest["sources"]:
        entry_id = entry["id"]
        tests = entry.get("applicable_tests") or []
        payload = _load_dataset_file(entry_id)
        probe: dict[str, Any] = {
            "id": entry_id,
            "verdict": entry.get("verdict"),
            "category": entry.get("category"),
            "applicable_tests": tests,
            "notes": entry.get("notes"),
        }
        if payload is None:
            if entry.get("hf_id"):
                probe["dataset_status"] = "missing_download"
            else:
                probe["dataset_status"] = "not_on_huggingface"
            dataset_probes.append(probe)
            continue

        probe["dataset_status"] = "present"
        probe["row_count"] = payload.get("row_count")
        probe["columns"] = payload.get("columns")
        if "injection_label_probe" in tests:
            probe["injection_label_probe"] = _probe_injection_labels(entry_id, payload)
        if "injection_heuristic_probe" in tests:
            probe["injection_heuristic_probe"] = _probe_injection_heuristic(entry_id, payload)
        if "bfcl_schema_probe" in tests:
            probe["bfcl_schema_probe"] = _probe_bfcl(payload)
        dataset_probes.append(probe)

    in_repo = {
        "routing_golden_pytest": _routing_golden_pytest(),
        "tenant_isolation_pytest": _tenant_isolation_pytest(),
        "security_golden_heuristics": _security_golden_heuristics(),
        "retrieval_golden_pytest": _retrieval_golden_pytest(),
        "tool_routing_pytest": _tool_routing_pytest(),
        "workflow_routing_pytest": _workflow_routing_pytest(),
    }

    verdict_counts = {"use": 0, "partial": 0, "skip": 0}
    for entry in manifest["sources"]:
        verdict = entry.get("verdict", "skip")
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "harness": "eggplant",
        "include_live_llm": include_live,
        "manifest_verdict_counts": verdict_counts,
        "download_status": download_status,
        "in_repo_tests": in_repo,
        "dataset_probes": dataset_probes,
        "summary": {
            "datasets_present": sum(1 for item in dataset_probes if item.get("dataset_status") == "present"),
            "datasets_missing": sum(1 for item in dataset_probes if item.get("dataset_status") == "missing_download"),
            "datasets_not_on_hf": sum(1 for item in dataset_probes if item.get("dataset_status") == "not_on_huggingface"),
            "in_repo_passed": all(
                block.get("passed")
                for block in in_repo.values()
                if isinstance(block, dict) and "passed" in block
            )
            and in_repo["routing_golden_pytest"]["passed"]
            and in_repo["tenant_isolation_pytest"]["passed"]
            and in_repo["retrieval_golden_pytest"]["passed"]
            and in_repo["tool_routing_pytest"]["passed"]
            and in_repo["workflow_routing_pytest"]["passed"],
        },
    }
    if include_connectivity:
        sys.path.insert(0, str(EGGPLANT_ROOT / "scripts"))
        from live_checks import check_remote_inference

        report["connectivity"] = check_remote_inference()
        report["summary"]["connectivity_passed"] = report["connectivity"].get("passed", False)
    if include_live:
        report["live_llm"] = _run_live_llm_smoke(
            base_url=base_url,
            limit=live_limit,
            timeout_s=live_timeout_s,
            auth_token=auth_token,
        )
        report["summary"]["live_llm_passed"] = report["live_llm"].get("passed", 0)
        report["summary"]["live_llm_failed"] = report["live_llm"].get("failed", 0)
    if include_indirect:
        sys.path.insert(0, str(EGGPLANT_ROOT / "scripts"))
        from live_checks import run_indirect_injection_live

        report["live_indirect_injection"] = run_indirect_injection_live(
            base_url=base_url,
            timeout_s=live_timeout_s,
            auth_token=auth_token,
        )
        report["summary"]["live_indirect_passed"] = report["live_indirect_injection"].get("passed", 0)
        report["summary"]["live_indirect_failed"] = report["live_indirect_injection"].get("failed", 0)
    if include_workflow:
        sys.path.insert(0, str(EGGPLANT_ROOT / "scripts"))
        from live_checks import run_workflow_smoke_live

        report["live_workflow"] = run_workflow_smoke_live(
            base_url=base_url,
            limit=min(3, live_limit),
            timeout_s=live_timeout_s,
            auth_token=auth_token,
        )
        report["summary"]["live_workflow_passed"] = report["live_workflow"].get("passed", 0)
        report["summary"]["live_workflow_failed"] = report["live_workflow"].get("failed", 0)
    return report


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Eggplant dataset evaluation",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Datasets on disk: **{summary['datasets_present']}**",
        f"- Missing HF downloads: **{summary['datasets_missing']}**",
        f"- Not on HuggingFace (manifest only): **{summary['datasets_not_on_hf']}**",
        f"- In-repo golden tests passed: **{summary['in_repo_passed']}**",
        "",
        "## Manifest verdicts",
        "",
        f"- use: {report['manifest_verdict_counts']['use']}",
        f"- partial: {report['manifest_verdict_counts']['partial']}",
        f"- skip: {report['manifest_verdict_counts']['skip']}",
        "",
        "## In-repo checks",
        "",
        f"- routing golden pytest: {'pass' if report['in_repo_tests']['routing_golden_pytest']['passed'] else 'fail'}",
        f"- tenant isolation pytest: {'pass' if report['in_repo_tests']['tenant_isolation_pytest']['passed'] else 'fail'}",
        f"- security golden heuristics: {'pass' if report['in_repo_tests']['security_golden_heuristics']['passed'] else 'fail'}",
        f"- retrieval golden pytest: {'pass' if report['in_repo_tests']['retrieval_golden_pytest']['passed'] else 'fail'}",
        f"- tool routing pytest: {'pass' if report['in_repo_tests']['tool_routing_pytest']['passed'] else 'fail'}",
        f"- workflow routing pytest: {'pass' if report['in_repo_tests']['workflow_routing_pytest']['passed'] else 'fail'}",
    ]
    if report.get("connectivity"):
        conn = report["connectivity"]
        lines.extend(
            [
                "",
                "## Remote inference connectivity",
                "",
                f"- Passed: **{conn.get('passed')}**",
                f"- LM host: `{conn.get('lm_host')}`",
            ]
        )
    if report.get("live_llm"):
        live = report["live_llm"]
        lines.extend(
            [
                "",
                "## Live LLM smoke (LM Studio / cloud via running app)",
                "",
                f"- Status: **{live.get('status')}**",
                f"- Base URL: `{live.get('base_url', 'n/a')}`",
                f"- Passed: **{live.get('passed', 0)}** / failed: **{live.get('failed', 0)}**",
                f"- Latency p50: **{live.get('latency_ms_p50', 'n/a')}** ms",
            ]
        )
    if report.get("live_indirect_injection"):
        live = report["live_indirect_injection"]
        lines.extend(
            [
                "",
                "## Live indirect injection (ingest + /rag_chat)",
                "",
                f"- Passed: **{live.get('passed', 0)}** / failed: **{live.get('failed', 0)}**",
            ]
        )
    if report.get("live_workflow"):
        live = report["live_workflow"]
        lines.extend(
            [
                "",
                "## Live workflow smoke (/workflow_chat)",
                "",
                f"- Passed: **{live.get('passed', 0)}** / failed: **{live.get('failed', 0)}**",
                f"- Latency p50: **{live.get('latency_ms_p50', 'n/a')}** ms",
            ]
        )
    lines.extend(
        [
            "",
            "## Dataset probes",
            "",
            "| ID | Status | Rows | Verdict | Notes |",
            "|----|--------|------|---------|-------|",
        ]
    )
    for probe in report["dataset_probes"]:
        lines.append(
            f"| {probe['id']} | {probe.get('dataset_status', 'n/a')} | "
            f"{probe.get('row_count', '—')} | {probe.get('verdict', '—')} | "
            f"{(probe.get('notes') or '')[:80]} |"
        )
    lines.extend(
        [
            "",
            "## How to re-run",
            "",
            "```bash",
            "make eggplant-setup",
            "make eggplant-download",
            "make eggplant-eval",
            "# Live sample against LM Studio (app must be running):",
            "make up-remote",
            "make eggplant-eval-live",
            "make eggplant-eval-live-full   # + indirect injection + workflow + connectivity",
            "make check-remote-inference",
            "make test-eval",
            "make model-accuracy-smoke",
            "```",
            "",
            "Full JSON artifact: see `docs/results/eggplant-latest.json`.",
            "",
            "## Download notes",
            "",
            "- **Gated HF sets** (GAIA, Qualifire, HackAPrompt): set `HF_TOKEN` and accept the Hub license, then re-run download.",
            "- **BFCL**: Hub repo layout may not expose a loadable split; use as a pattern reference only.",
            "- **GitHub-only benchmarks** (WebArena, SWE-bench runtime, AgentBench): listed in manifest with skip reasons.",
            "",
            "This harness runs **offline probes** and in-repo golden tests by default.",
            "Use `make eggplant-eval-live` to POST a small prompt sample to `/chat` on a running stack",
            "(e.g. `make up-remote` → LM Studio on :1234).",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run eggplant offline dataset verification.")
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help="POST a small prompt sample to /chat on a running app (LM Studio, Groq, etc.).",
    )
    parser.add_argument(
        "--live-indirect",
        action="store_true",
        help="Ingest malicious docs and query via /rag_chat (requires running app).",
    )
    parser.add_argument(
        "--live-workflow",
        action="store_true",
        help="POST workflow golden queries to /workflow_chat (requires running app).",
    )
    parser.add_argument(
        "--connectivity-check",
        action="store_true",
        help="Check LM Studio / Ollama reachability before live tests.",
    )
    parser.add_argument(
        "--live-full",
        action="store_true",
        help="Shorthand for --live-llm --live-indirect --live-workflow --connectivity-check.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"),
        help="Running Personal AI base URL (default: BASE_URL env or http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--live-limit",
        type=int,
        default=int(os.environ.get("EGGPLANT_LIVE_LIMIT", "12")),
        help="Max live /chat prompts (default: 12).",
    )
    parser.add_argument(
        "--live-timeout",
        type=float,
        default=float(os.environ.get("EGGPLANT_LIVE_TIMEOUT", "180")),
        help="Per-request timeout seconds (default: 180 for local LM Studio).",
    )
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("AUTH_TOKEN", ""),
        help="Optional Bearer JWT when AUTH_DISABLED=false.",
    )
    args = parser.parse_args()
    live_full = args.live_full
    include_live = args.live_llm or live_full
    include_indirect = args.live_indirect or live_full
    include_workflow = args.live_workflow or live_full
    include_connectivity = args.connectivity_check or live_full

    sys.path.insert(0, str(REPO_ROOT))
    report = _build_report(
        include_live=include_live,
        include_indirect=include_indirect,
        include_workflow=include_workflow,
        include_connectivity=include_connectivity,
        base_url=args.base_url,
        live_limit=max(1, args.live_limit),
        live_timeout_s=max(30.0, args.live_timeout),
        auth_token=args.auth_token.strip(),
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = RESULTS_DIR / f"eggplant-{stamp}.json"
    latest_json = DOCS_RESULTS_DIR / "eggplant-latest.json"
    md_path = REPO_ROOT / "docs" / "eggplant-eval.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report, md_path)

    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {latest_json}")
    print(f"Wrote {md_path}")
    return 0 if report["summary"]["in_repo_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
