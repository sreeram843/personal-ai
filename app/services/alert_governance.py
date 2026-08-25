"""Suppress duplicate scheduled-report alerts within a refractory window."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings

TIER_ACTIONABLE = "actionable"
TIER_INFORMATIONAL = "informational"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_tier(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw == TIER_INFORMATIONAL:
        return TIER_INFORMATIONAL
    return TIER_ACTIONABLE


def condition_key(*, user_id: str, schedule_id: str, prompt: str) -> str:
    digest = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()[:16]
    return f"{user_id}:{schedule_id}:{digest}"


def schedule_tier(schedule: Any) -> str:
    """Default schedules to actionable; honor payload/metadata tier when set."""
    candidates: list[Any] = [getattr(schedule, "tier", None)]
    metadata = getattr(schedule, "metadata", None)
    if isinstance(metadata, dict):
        candidates.append(metadata.get("tier"))
        candidates.append(metadata.get("alert_tier"))
    payload = getattr(schedule, "payload", None)
    if isinstance(payload, dict):
        candidates.append(payload.get("tier"))
        nested = payload.get("metadata")
        if isinstance(nested, dict):
            candidates.append(nested.get("tier"))
            candidates.append(nested.get("alert_tier"))
    for raw in candidates:
        if raw is None or raw == "":
            continue
        normalized = str(raw).strip().lower()
        if normalized == TIER_INFORMATIONAL:
            return TIER_INFORMATIONAL
        if normalized == TIER_ACTIONABLE:
            return TIER_ACTIONABLE
    return TIER_ACTIONABLE


class AlertGovernance:
    """JSON-backed refractory window so the same condition does not spam."""

    def __init__(self, *, file_path: str, refractory_minutes: int) -> None:
        self._path = Path(file_path)
        self.refractory_minutes = max(1, int(refractory_minutes))
        self.suppressed = 0
        self._conditions: Dict[str, Dict[str, Any]] = {}
        self._load()

    def window_minutes(self, *, tier: str, last_tier: Optional[str] = None) -> int:
        current = _normalize_tier(tier)
        previous = _normalize_tier(last_tier) if last_tier else None
        # Informational alerts (and informational repeats) use a longer window.
        if current == TIER_INFORMATIONAL or previous == TIER_INFORMATIONAL:
            return self.refractory_minutes * 2
        return self.refractory_minutes

    def should_notify(
        self,
        condition_key: str,
        *,
        tier: str,
        now: Optional[datetime] = None,
    ) -> bool:
        current = now or _utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        normalized = _normalize_tier(tier)
        record = self._conditions.get(condition_key)
        if not record:
            return True
        last_fired = _parse_iso(record.get("last_fired_at"))
        if last_fired is None:
            return True
        last_tier = _normalize_tier(record.get("last_tier"))
        # Escalation from informational → actionable should still notify.
        if last_tier == TIER_INFORMATIONAL and normalized == TIER_ACTIONABLE:
            return True
        window = timedelta(minutes=self.window_minutes(tier=normalized, last_tier=last_tier))
        if current < last_fired + window:
            self.suppressed += 1
            return False
        return True

    def record_fire(
        self,
        condition_key: str,
        *,
        tier: str,
        now: Optional[datetime] = None,
    ) -> None:
        current = now or _utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        self._conditions[condition_key] = {
            "last_fired_at": _iso(current),
            "last_tier": _normalize_tier(tier),
        }
        self._save()

    def _load(self) -> None:
        if not self._path.exists():
            self._conditions = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            self._conditions = {}
            return
        if isinstance(raw, dict) and isinstance(raw.get("conditions"), dict):
            payload = raw["conditions"]
        elif isinstance(raw, dict):
            payload = raw
        else:
            payload = {}
        conditions: Dict[str, Dict[str, Any]] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                conditions[str(key)] = value
        self._conditions = conditions

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"conditions": self._conditions}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_alert_governance(
    *,
    file_path: Optional[str] = None,
    refractory_minutes: Optional[int] = None,
) -> AlertGovernance:
    settings = get_settings()
    return AlertGovernance(
        file_path=file_path or settings.alert_governance_path,
        refractory_minutes=(
            settings.alert_refractory_minutes if refractory_minutes is None else refractory_minutes
        ),
    )


__all__ = [
    "TIER_ACTIONABLE",
    "TIER_INFORMATIONAL",
    "AlertGovernance",
    "build_alert_governance",
    "condition_key",
    "schedule_tier",
]
