"""Per-user implicit skill preference counts (usage history).

Separate from SkillStore `_pref_` records. JSON shape: `{user_id: {skill_id: count}}`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillImplicitStore:
    """File-backed usage counts used to break ties among trigger matches."""

    def __init__(self, *, file_path: str) -> None:
        self._path = Path(file_path)

    def record(self, user_id: str, skill_id: str) -> None:
        data = self._load()
        user_counts = data.setdefault(user_id, {})
        user_counts[skill_id] = int(user_counts.get(skill_id, 0)) + 1
        self._write(data)

    def preferred_among(self, user_id: str, skill_ids: List[str]) -> Optional[str]:
        """Return the unique skill_id with the highest count, else None.

        None means: no history, all zero, or a tie for the highest count so the
        caller should keep original (bundled) order.
        """
        if not skill_ids:
            return None
        counts = self._load().get(user_id) or {}
        scored = [(int(counts.get(skill_id, 0)), skill_id) for skill_id in skill_ids]
        best = max(count for count, _ in scored)
        if best <= 0:
            return None
        winners = [skill_id for count, skill_id in scored if count == best]
        if len(winners) != 1:
            return None
        return winners[0]

    def _load(self) -> Dict[str, Dict[str, int]]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, Dict[str, int]] = {}
        for user_id, skills in raw.items():
            if not isinstance(skills, dict):
                continue
            parsed: Dict[str, int] = {}
            for skill_id, value in skills.items():
                if isinstance(value, bool) or not isinstance(value, int):
                    continue
                parsed[str(skill_id)] = value
            out[str(user_id)] = parsed
        return out

    def _write(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_skill_implicit_store(*, file_path: str) -> SkillImplicitStore:
    return SkillImplicitStore(file_path=file_path)


__all__ = [
    "SkillImplicitStore",
    "build_skill_implicit_store",
]
