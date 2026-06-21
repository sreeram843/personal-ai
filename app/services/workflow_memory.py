from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class WorkflowMemoryStore:
    """Conversation memory for orchestrated runs, scoped per user."""

    def __init__(self, *, file_path: str, max_entries_per_conversation: int = 24) -> None:
        self._path = Path(file_path)
        self._max_entries = max_entries_per_conversation
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @staticmethod
    def _namespace(user_id: Optional[str], conversation_id: str) -> str:
        if user_id:
            return f"{user_id}:{conversation_id}"
        return conversation_id

    async def get_summary(self, conversation_id: str, *, user_id: Optional[str] = None, limit: int = 6) -> str:
        if not conversation_id:
            return ""
        async with self._get_lock():
            data = await asyncio.to_thread(self._read_all)
        conversation = data.get(self._namespace(user_id, conversation_id), {})
        entries = conversation.get("entries", [])[-limit:]
        if not entries:
            return ""

        lines = ["## Prior Workflow Memory"]
        for entry in entries:
            agent = str(entry.get("agent", "agent"))
            title = str(entry.get("title", "memory"))
            summary = str(entry.get("summary", "")).strip()
            if summary:
                lines.append(f"- {agent} / {title}: {summary}")
        return "\n".join(lines)

    async def append_entries(
        self,
        conversation_id: str,
        entries: List[Dict[str, Any]],
        *,
        user_id: Optional[str] = None,
    ) -> None:
        if not conversation_id or not entries:
            return
        namespace = self._namespace(user_id, conversation_id)
        async with self._get_lock():
            data = await asyncio.to_thread(self._read_all)
            conversation = data.setdefault(namespace, {"entries": [], "updated_at": _utc_now()})
            current_entries = conversation.setdefault("entries", [])
            for entry in entries:
                current_entries.append(
                    {
                        "agent": entry.get("agent", "agent"),
                        "title": entry.get("title", "memory"),
                        "summary": entry.get("summary", ""),
                        "created_at": entry.get("created_at", _utc_now()),
                    }
                )
            conversation["entries"] = current_entries[-self._max_entries :]
            conversation["updated_at"] = _utc_now()
            await asyncio.to_thread(self._write_all, data)

    def _read_all(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_all(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class RedisWorkflowMemoryStore(WorkflowMemoryStore):
    """Redis-backed workflow memory for stateless API replicas."""

    def __init__(
        self,
        *,
        redis_url: str,
        key_prefix: str = "personal-ai:workflow-memory",
        max_entries_per_conversation: int = 24,
        ttl_seconds: int = 60 * 60 * 24 * 14,
    ) -> None:
        super().__init__(file_path="memory/workflow_sessions.json", max_entries_per_conversation=max_entries_per_conversation)
        import redis

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    def _redis_key(self) -> str:
        return self._key_prefix

    def _read_all(self) -> Dict[str, Any]:
        raw = self._redis.get(self._redis_key())
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _write_all(self, data: Dict[str, Any]) -> None:
        self._redis.setex(self._redis_key(), self._ttl_seconds, json.dumps(data))


def build_workflow_memory_store(
    *,
    file_path: str,
    max_entries: int,
    backend: str,
    redis_url: Optional[str],
) -> WorkflowMemoryStore:
    if backend == "redis" and redis_url:
        return RedisWorkflowMemoryStore(redis_url=redis_url, max_entries_per_conversation=max_entries)
    return WorkflowMemoryStore(file_path=file_path, max_entries_per_conversation=max_entries)
