from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class WorkflowMemoryStore:
    """File-backed conversation memory for orchestrated runs."""

    def __init__(self, *, file_path: str, max_entries_per_conversation: int = 24) -> None:
        self._path = Path(file_path)
        self._max_entries = max_entries_per_conversation
        self._lock = asyncio.Lock()

    async def get_summary(self, conversation_id: str, limit: int = 6) -> str:
        if not conversation_id:
            return ""
        async with self._lock:
            data = await asyncio.to_thread(self._read_all)
        conversation = data.get(conversation_id, {})
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

    async def append_entries(self, conversation_id: str, entries: List[Dict[str, Any]]) -> None:
        if not conversation_id or not entries:
            return
        async with self._lock:
            data = await asyncio.to_thread(self._read_all)
            conversation = data.setdefault(conversation_id, {"entries": [], "updated_at": _utc_now()})
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


__all__ = ["WorkflowMemoryStore"]