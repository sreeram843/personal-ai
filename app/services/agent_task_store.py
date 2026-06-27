"""Persist agent tasks (planned tools, follow-ups) per user."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

AgentTaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]
AgentTaskSource = Literal["planned_tool", "user", "skill"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class AgentTaskRecord:
    id: str
    user_id: str
    title: str
    detail: str = ""
    status: AgentTaskStatus = "pending"
    source: AgentTaskSource = "user"
    tool_id: Optional[str] = None
    conversation_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AgentTaskRecord":
        return cls(
            id=str(raw.get("id") or ""),
            user_id=str(raw.get("user_id") or ""),
            title=str(raw.get("title") or "Task"),
            detail=str(raw.get("detail") or ""),
            status=str(raw.get("status") or "pending"),  # type: ignore[arg-type]
            source=str(raw.get("source") or "user"),  # type: ignore[arg-type]
            tool_id=raw.get("tool_id"),
            conversation_id=raw.get("conversation_id"),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
        )


class AgentTaskStore:
    def __init__(self, *, file_path: str, max_tasks_per_user: int = 40) -> None:
        self._path = Path(file_path)
        self._max_tasks = max_tasks_per_user

    def list_for_user(self, user_id: str, *, conversation_id: Optional[str] = None) -> List[AgentTaskRecord]:
        items = [item for item in self._load_all() if item.user_id == user_id]
        if conversation_id:
            items = [item for item in items if item.conversation_id == conversation_id]
        return sorted(items, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def create(
        self,
        *,
        user_id: str,
        title: str,
        detail: str = "",
        source: AgentTaskSource = "user",
        tool_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> AgentTaskRecord:
        now = _utc_now()
        task = AgentTaskRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title.strip() or "Task",
            detail=detail.strip(),
            status="pending",
            source=source,
            tool_id=tool_id,
            conversation_id=conversation_id,
            created_at=now,
            updated_at=now,
        )
        items = self._load_all()
        items.append(task)
        self._trim_user(items, user_id)
        self._write_all(items)
        return task

    def update_status(self, task_id: str, *, user_id: str, status: AgentTaskStatus) -> Optional[AgentTaskRecord]:
        items = self._load_all()
        updated: Optional[AgentTaskRecord] = None
        for idx, item in enumerate(items):
            if item.id != task_id or item.user_id != user_id:
                continue
            item.status = status
            item.updated_at = _utc_now()
            items[idx] = item
            updated = item
            break
        if updated is None:
            return None
        self._write_all(items)
        return updated

    def delete(self, task_id: str, *, user_id: str) -> bool:
        items = self._load_all()
        next_items = [item for item in items if not (item.id == task_id and item.user_id == user_id)]
        if len(next_items) == len(items):
            return False
        self._write_all(next_items)
        return True

    def record_planned_tools(
        self,
        *,
        user_id: str,
        conversation_id: Optional[str],
        planned_tools: List[Dict[str, Any]],
    ) -> List[AgentTaskRecord]:
        created: List[AgentTaskRecord] = []
        for planned in planned_tools:
            tool_id = str(planned.get("tool_id") or "")
            name = str(planned.get("name") or tool_id or "Planned tool")
            reason = str(planned.get("reason") or "Plan mode")
            task = self.create(
                user_id=user_id,
                title=f"Plan: {name}",
                detail=reason,
                source="planned_tool",
                tool_id=tool_id or None,
                conversation_id=conversation_id,
            )
            created.append(task)
        return created

    def _trim_user(self, items: List[AgentTaskRecord], user_id: str) -> None:
        user_items = [item for item in items if item.user_id == user_id]
        if len(user_items) <= self._max_tasks:
            return
        keep_ids = {item.id for item in sorted(user_items, key=lambda x: x.updated_at, reverse=True)[: self._max_tasks]}
        items[:] = [item for item in items if item.user_id != user_id or item.id in keep_ids]

    def _load_all(self) -> List[AgentTaskRecord]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        return [AgentTaskRecord.from_dict(item) for item in raw if isinstance(item, dict)]

    def _write_all(self, items: List[AgentTaskRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([asdict(item) for item in items], indent=2), encoding="utf-8")


def build_agent_task_store(*, file_path: str, max_tasks_per_user: int = 40) -> AgentTaskStore:
    return AgentTaskStore(file_path=file_path, max_tasks_per_user=max_tasks_per_user)


__all__ = ["AgentTaskRecord", "AgentTaskStore", "build_agent_task_store"]
