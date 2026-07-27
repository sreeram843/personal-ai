"""Agent Lab, Phase 2: a shared run tracer.

Every lab agent from Phase 3 onward accepts an optional `RunTrace` and
records into it: one entry per LLM call and one per tool/code execution,
each with its own duration. Traces persist to disk as JSON so a run can be
replayed later via GET /agent/lab/runs/{id} — this is what turns "the agent
did something" into "here is exactly what it saw and did, in order."
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceEvent:
    kind: str  # "llm_call" | "tool_call" | "note"
    index: int
    started_at: str
    duration_ms: float
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunTrace:
    trace_id: str
    agent: str
    query: str
    user_id: Optional[str]
    created_at: str
    status: str = "running"  # running | done | error
    answer: Optional[str] = None
    steps: int = 0
    error: Optional[str] = None
    events: List[TraceEvent] = field(default_factory=list)

    @contextmanager
    def llm_call(self, *, request: Dict[str, Any]) -> Iterator["_EventRecorder"]:
        """Wrap one LLM round-trip; assign `.response` on the yielded recorder."""
        recorder = _EventRecorder()
        started = time.monotonic()
        try:
            yield recorder
        finally:
            self.events.append(
                TraceEvent(
                    kind="llm_call",
                    index=len(self.events),
                    started_at=_utc_now(),
                    duration_ms=round((time.monotonic() - started) * 1000, 1),
                    data={"request": request, "response": recorder.response},
                )
            )

    def record_tool_call(
        self, *, name: str, arguments: Dict[str, Any], result: Any, duration_ms: float
    ) -> None:
        self.events.append(
            TraceEvent(
                kind="tool_call",
                index=len(self.events),
                started_at=_utc_now(),
                duration_ms=round(duration_ms, 1),
                data={"name": name, "arguments": arguments, "result": result},
            )
        )

    def note(self, message: str) -> None:
        self.events.append(
            TraceEvent(
                kind="note",
                index=len(self.events),
                started_at=_utc_now(),
                duration_ms=0.0,
                data={"message": message},
            )
        )

    def finish(self, *, answer: str, steps: int) -> None:
        self.status = "done"
        self.answer = answer
        self.steps = steps

    def fail(self, *, error: str, steps: int) -> None:
        self.status = "error"
        self.error = error
        self.steps = steps

    def to_dict(self) -> Dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "events"},
            "events": [asdict(event) for event in self.events],
        }

    def summary(self) -> Dict[str, Any]:
        """Compact form for list views — no event payloads."""
        return {
            "trace_id": self.trace_id,
            "agent": self.agent,
            "query": self.query,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "status": self.status,
            "steps": self.steps,
            "event_count": len(self.events),
        }


@dataclass
class _EventRecorder:
    """Mutable box so `llm_call()` can attach the response after the request runs."""

    response: Any = None


class TraceStore:
    """Disk-backed trace persistence, one JSON file per trace."""

    def __init__(self, storage_path: str = "memory/agent_lab/traces") -> None:
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)

    def new_trace(self, *, agent: str, query: str, user_id: Optional[str]) -> RunTrace:
        return RunTrace(
            trace_id=f"trace_{uuid4().hex[:12]}",
            agent=agent,
            query=query,
            user_id=user_id,
            created_at=_utc_now(),
        )

    def save(self, trace: RunTrace) -> None:
        file_path = self._path / f"{trace.trace_id}.json"
        file_path.write_text(json.dumps(trace.to_dict(), indent=2, default=str))

    def get(self, trace_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._path / f"{trace_id}.json"
        if not file_path.exists():
            return None
        return json.loads(file_path.read_text())

    def list_recent(self, *, agent: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        files = sorted(self._path.glob("trace_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        summaries: List[Dict[str, Any]] = []
        for file_path in files:
            try:
                data = json.loads(file_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if agent and data.get("agent") != agent:
                continue
            summaries.append(
                {
                    "trace_id": data.get("trace_id"),
                    "agent": data.get("agent"),
                    "query": data.get("query"),
                    "user_id": data.get("user_id"),
                    "created_at": data.get("created_at"),
                    "status": data.get("status"),
                    "steps": data.get("steps"),
                    "event_count": len(data.get("events") or []),
                }
            )
            if len(summaries) >= limit:
                break
        return summaries


_default_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    global _default_store
    if _default_store is None:
        _default_store = TraceStore()
    return _default_store


__all__ = ["RunTrace", "TraceEvent", "TraceStore", "get_trace_store"]
