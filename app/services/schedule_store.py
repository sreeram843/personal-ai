"""Persist scheduled workflow reports and track next run times."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class ScheduledReport:
    id: str
    user_id: str
    title: str
    prompt: str
    interval_minutes: int
    enabled: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_run_id: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ScheduledReport":
        return cls(
            id=str(raw.get("id") or ""),
            user_id=str(raw.get("user_id") or ""),
            title=str(raw.get("title") or "Scheduled report"),
            prompt=str(raw.get("prompt") or ""),
            interval_minutes=int(raw.get("interval_minutes") or 1440),
            enabled=bool(raw.get("enabled", True)),
            last_run_at=raw.get("last_run_at"),
            next_run_at=raw.get("next_run_at"),
            last_run_id=raw.get("last_run_id"),
        )


class ScheduleStore:
    def __init__(self, *, file_path: str) -> None:
        self._path = Path(file_path)

    def list_for_user(self, user_id: str) -> List[ScheduledReport]:
        return [item for item in self._load_all() if item.user_id == user_id]

    def get(self, schedule_id: str) -> Optional[ScheduledReport]:
        for item in self._load_all():
            if item.id == schedule_id:
                return item
        return None

    def create(
        self,
        *,
        user_id: str,
        title: str,
        prompt: str,
        interval_minutes: int,
    ) -> ScheduledReport:
        now = _utc_now()
        report = ScheduledReport(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title.strip() or "Scheduled report",
            prompt=prompt.strip(),
            interval_minutes=max(15, interval_minutes),
            enabled=True,
            next_run_at=_iso(now),
        )
        items = self._load_all()
        items.append(report)
        self._save_all(items)
        return report

    def delete(self, *, user_id: str, schedule_id: str) -> bool:
        items = self._load_all()
        kept = [item for item in items if not (item.id == schedule_id and item.user_id == user_id)]
        if len(kept) == len(items):
            return False
        self._save_all(kept)
        return True

    def list_due(self, *, now: Optional[datetime] = None) -> List[ScheduledReport]:
        current = now or _utc_now()
        due: List[ScheduledReport] = []
        for item in self._load_all():
            if not item.enabled:
                continue
            next_run = _parse_iso(item.next_run_at)
            if next_run is None or next_run <= current:
                due.append(item)
        return due

    def mark_run(self, schedule_id: str, *, run_id: str) -> None:
        items = self._load_all()
        now = _utc_now()
        updated: List[ScheduledReport] = []
        for item in items:
            if item.id != schedule_id:
                updated.append(item)
                continue
            item.last_run_at = _iso(now)
            item.last_run_id = run_id
            item.next_run_at = _iso(now + timedelta(minutes=item.interval_minutes))
            updated.append(item)
        self._save_all(updated)

    def _load_all(self) -> List[ScheduledReport]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [ScheduledReport.from_dict(item) for item in raw if isinstance(item, dict)]

    def _save_all(self, items: List[ScheduledReport]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items]
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_schedule_store(*, file_path: str) -> ScheduleStore:
    return ScheduleStore(file_path=file_path)


__all__ = ["ScheduledReport", "ScheduleStore", "build_schedule_store"]
