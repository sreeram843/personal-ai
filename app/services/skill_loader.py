"""User skills and bundled workflow definitions."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class SkillRecord:
    id: str
    name: str
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    system_addendum: str = ""
    enabled: bool = True
    bundled: bool = False
    pick_only: bool = False
    user_id: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "SkillRecord":
        triggers = raw.get("triggers") or []
        tools = raw.get("allowed_tools") or []
        return cls(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or "Skill"),
            description=str(raw.get("description") or ""),
            triggers=[str(item).strip().lower() for item in triggers if str(item).strip()],
            allowed_tools=[str(item).strip() for item in tools if str(item).strip()],
            system_addendum=str(raw.get("system_addendum") or raw.get("body") or "").strip(),
            enabled=bool(raw.get("enabled", True)),
            bundled=bool(raw.get("bundled", False)),
            pick_only=bool(raw.get("pick_only", False)),
            user_id=raw.get("user_id"),
        )


class SkillStore:
    """Persist user-authored skills."""

    def __init__(self, *, file_path: str) -> None:
        self._path = Path(file_path)

    def list_for_user(self, user_id: str) -> List[SkillRecord]:
        user_skills = self._load_all()
        return [item for item in user_skills if item.user_id == user_id and not item.id.startswith("_pref_")]

    def get_preference(self, user_id: str, skill_id: str) -> Optional[bool]:
        for item in self._load_all():
            if item.user_id == user_id and item.id == f"_pref_{skill_id}":
                return item.enabled
        return None

    def set_bundled_preference(self, user_id: str, skill_id: str, *, enabled: bool) -> None:
        pref_id = f"_pref_{skill_id}"
        items = self._load_all()
        found = False
        for idx, item in enumerate(items):
            if item.user_id == user_id and item.id == pref_id:
                item.enabled = enabled
                items[idx] = item
                found = True
                break
        if not found:
            items.append(
                SkillRecord(
                    id=pref_id,
                    user_id=user_id,
                    name=f"preference:{skill_id}",
                    enabled=enabled,
                    bundled=False,
                )
            )
        self._write_all(items)

    def get(self, skill_id: str, *, user_id: str) -> Optional[SkillRecord]:
        for item in self._load_all():
            if item.id == skill_id and item.user_id == user_id:
                return item
        return None

    def create(
        self,
        *,
        user_id: str,
        name: str,
        description: str = "",
        triggers: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None,
        system_addendum: str = "",
        pick_only: bool = False,
    ) -> SkillRecord:
        skill = SkillRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name.strip(),
            description=description.strip(),
            triggers=[t.strip().lower() for t in (triggers or []) if t.strip()],
            allowed_tools=[t.strip() for t in (allowed_tools or []) if t.strip()],
            system_addendum=system_addendum.strip(),
            enabled=True,
            bundled=False,
            pick_only=pick_only,
        )
        items = self._load_all()
        items.append(skill)
        self._write_all(items)
        return skill

    def update(
        self,
        skill_id: str,
        *,
        user_id: str,
        enabled: Optional[bool] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        triggers: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None,
        system_addendum: Optional[str] = None,
        pick_only: Optional[bool] = None,
    ) -> Optional[SkillRecord]:
        items = self._load_all()
        updated: Optional[SkillRecord] = None
        for idx, item in enumerate(items):
            if item.id != skill_id or item.user_id != user_id:
                continue
            if enabled is not None:
                item.enabled = enabled
            if name is not None:
                item.name = name.strip()
            if description is not None:
                item.description = description.strip()
            if triggers is not None:
                item.triggers = [t.strip().lower() for t in triggers if t.strip()]
            if allowed_tools is not None:
                item.allowed_tools = [t.strip() for t in allowed_tools if t.strip()]
            if system_addendum is not None:
                item.system_addendum = system_addendum.strip()
            if pick_only is not None:
                item.pick_only = pick_only
            items[idx] = item
            updated = item
            break
        if updated is None:
            return None
        self._write_all(items)
        return updated

    def delete(self, skill_id: str, *, user_id: str) -> bool:
        items = self._load_all()
        next_items = [item for item in items if not (item.id == skill_id and item.user_id == user_id)]
        if len(next_items) == len(items):
            return False
        self._write_all(next_items)
        return True

    def _load_all(self) -> List[SkillRecord]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        return [SkillRecord.from_dict(item) for item in raw if isinstance(item, dict)]

    def _write_all(self, items: List[SkillRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items]
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_simple_yaml(block: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current_list: Optional[str] = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list:
            data.setdefault(current_list, []).append(stripped[2:].strip().strip('"').strip("'"))
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not value:
                current_list = key
                data.setdefault(key, [])
            else:
                current_list = None
                data[key] = value
    return data


def load_bundled_skills(root: Path) -> List[SkillRecord]:
    skills: List[SkillRecord] = []
    if not root.exists():
        return skills
    for path in sorted(root.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text.strip())
        if not match:
            continue
        meta = _parse_simple_yaml(match.group(1))
        body = match.group(2).strip()
        skill_id = str(meta.get("id") or path.parent.name)
        triggers = meta.get("triggers") or []
        if isinstance(triggers, str):
            triggers = [triggers]
        allowed = meta.get("allowed_tools") or []
        if isinstance(allowed, str):
            allowed = [allowed]
        skills.append(
            SkillRecord(
                id=skill_id,
                name=str(meta.get("name") or skill_id),
                description=str(meta.get("description") or ""),
                triggers=[str(item).lower() for item in triggers],
                allowed_tools=[str(item) for item in allowed],
                system_addendum=body,
                enabled=True,
                bundled=True,
            )
        )
    return skills


@dataclass
class ResolvedSkill:
    skill: SkillRecord
    matched_by: str


class SkillCatalog:
    def __init__(self, *, bundled_root: str, store: SkillStore) -> None:
        self._bundled_root = Path(bundled_root)
        self._store = store
        self._bundled = load_bundled_skills(self._bundled_root)

    def list_for_user(self, user_id: str) -> List[SkillRecord]:
        user_skills = self._store.list_for_user(user_id)
        user_by_id = {item.id: item for item in user_skills}
        merged: List[SkillRecord] = []
        for bundled in self._bundled:
            copy = SkillRecord.from_dict(asdict(bundled))
            pref = self._store.get_preference(user_id, bundled.id)
            if pref is not None:
                copy.enabled = pref
            merged.append(copy)
        for custom in user_skills:
            if not any(item.id == custom.id for item in merged):
                merged.append(custom)
        return merged

    def resolve(self, query: str, *, user_id: str) -> Optional[ResolvedSkill]:
        text = (query or "").strip()
        lowered = text.lower()
        if not text:
            return None

        slash = lowered
        if slash.startswith("/"):
            slash = slash[1:].split(maxsplit=1)[0].strip()

        for skill in self.list_for_user(user_id):
            if not skill.enabled:
                continue
            if skill.pick_only:
                continue
            if slash and (skill.id.lower() == slash or skill.name.lower().replace(" ", "-") == slash):
                return ResolvedSkill(skill=skill, matched_by=f"/{slash}")
            for trigger in skill.triggers:
                if trigger and trigger in lowered:
                    return ResolvedSkill(skill=skill, matched_by=trigger)
        return None

    def get_by_id(self, user_id: str, skill_id: str) -> Optional[SkillRecord]:
        needle = skill_id.strip()
        if not needle:
            return None
        for skill in self.list_for_user(user_id):
            if skill.id == needle:
                return skill
        return None


def build_skill_store(*, file_path: str) -> SkillStore:
    return SkillStore(file_path=file_path)


def build_skill_catalog(*, bundled_root: str, store: SkillStore) -> SkillCatalog:
    return SkillCatalog(bundled_root=bundled_root, store=store)


__all__ = [
    "ResolvedSkill",
    "SkillCatalog",
    "SkillRecord",
    "SkillStore",
    "build_skill_catalog",
    "build_skill_store",
    "load_bundled_skills",
]
