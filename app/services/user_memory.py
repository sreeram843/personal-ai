"""Cross-session user memory summaries (compact continuity block for prompts)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class UserMemoryStore:
    """Per-user rolling memory notes stored on disk (or Redis wrapper later)."""

    def __init__(self, *, file_path: str, max_entries_per_user: int = 12) -> None:
        self._path = Path(file_path)
        self._max_entries = max_entries_per_user

    def record_turn(
        self,
        user_id: str,
        *,
        user_message: str,
        assistant_message: str,
    ) -> None:
        if not user_id:
            return
        user_text = " ".join((user_message or "").split())[:200]
        assistant_text = " ".join((assistant_message or "").split())[:280]
        if not user_text:
            return
        data = self._read_all()
        bucket = data.setdefault(user_id, {"entries": [], "updated_at": _utc_now()})
        entries: List[Dict[str, Any]] = bucket.setdefault("entries", [])
        entries.append(
            {
                "user": user_text,
                "assistant": assistant_text,
                "created_at": _utc_now(),
            }
        )
        bucket["entries"] = entries[-self._max_entries :]
        bucket["updated_at"] = _utc_now()
        self._write_all(data)

    def get_memory_block(
        self,
        user_id: Optional[str],
        *,
        limit: int = 5,
        consolidation_service: Optional[Any] = None,
    ) -> str:
        if not user_id:
            return ""
        data = self._read_all()
        bucket = data.get(user_id) or {}
        entries = bucket.get("entries") or []
        facts = bucket.get("facts") or []
        consolidation_lines = _consolidation_fact_lines(consolidation_service, user_id)
        if not entries and not facts and not consolidation_lines:
            return ""
        lines = ["## User memory (cross-session continuity)"]
        for fact in facts[-4:]:
            text = str(fact).strip()
            if text:
                lines.append(f"- {text}")
        for entry in entries[-limit:]:
            user_line = str(entry.get("user") or "").strip()
            assistant_line = str(entry.get("assistant") or "").strip()
            if user_line:
                lines.append(f"- User asked: {user_line}")
            if assistant_line:
                lines.append(f"  Assistant replied: {assistant_line}")
        lines.extend(consolidation_lines)
        lines.append("Use for continuity only; prioritize the latest message.")
        return "\n".join(lines)

    def record_fact(self, user_id: str, fact: str) -> None:
        cleaned = " ".join((fact or "").split()).strip()
        if not user_id or not cleaned:
            return
        data = self._read_all()
        bucket = data.setdefault(user_id, {"entries": [], "facts": [], "updated_at": _utc_now()})
        facts: List[str] = [str(item).strip() for item in bucket.setdefault("facts", []) if str(item).strip()]
        if cleaned not in facts:
            facts.append(cleaned)
        bucket["facts"] = facts[-8:]
        bucket["updated_at"] = _utc_now()
        self._write_all(data)

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


def build_user_memory_store(*, file_path: str, max_entries: int) -> UserMemoryStore:
    return UserMemoryStore(file_path=file_path, max_entries_per_user=max_entries)


def _consolidation_fact_lines(consolidation_service: Optional[Any], user_id: str) -> List[str]:
    if consolidation_service is None:
        return []
    lines: List[str] = []
    for entry in consolidation_service.retrieve_relevant(user_id, limit=4):
        freshness = float(getattr(entry, "freshness", 1.0) or 0.0)
        confidence = float(getattr(entry, "confidence", 0.0) or 0.0)
        is_stale = bool(entry.is_stale()) if hasattr(entry, "is_stale") else False
        if freshness < 0.2 or confidence < 0.3 or is_stale:
            continue
        text = str(getattr(entry, "content", "") or "").strip()
        if text:
            lines.append(f"- {text} (confidence {confidence:.2f})")
    return lines


def extract_memory_facts_heuristic(user_message: str, assistant_message: str) -> List[str]:
    """Extract durable user preferences/tasks from natural phrasing."""
    facts: List[str] = []
    text = (user_message or "").strip()
    lowered = text.lower()
    triggers = (
        "remember that",
        "always use",
        "i prefer",
        "my name is",
        "call me",
        "don't forget",
        "from now on",
    )
    for trigger in triggers:
        if trigger in lowered:
            facts.append(text[:220])
            break
    if "timezone" in lowered or "time zone" in lowered:
        facts.append(text[:220])
    return facts[:2]


__all__ = ["UserMemoryStore", "build_user_memory_store", "extract_memory_facts_heuristic"]
