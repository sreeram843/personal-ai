from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Tuple

from api.persona_loader import (
    PersonaDefinition,
    PersonaNotFoundError,
    available_personas,
    load_persona,
)

PROFILE_PATH = Path("memory/profile.json")
DEFAULT_PERSONA = "default"


@dataclass
class PersonaState:
    definition: PersonaDefinition
    banned_word_patterns: List[re.Pattern[str]]


class PersonaManager:
    """In-memory persona registry with hot-reload support."""

    def __init__(self, profile_path: Path | None = None) -> None:
        self._profile_path = profile_path or PROFILE_PATH
        self._lock = RLock()
        self._profile: Dict[str, object] = self._load_profile()
        self._state: PersonaState = self._load_initial_state()

    # ------------------------------------------------------------------
    # Profile handling
    def _load_profile(self) -> Dict[str, object]:
        if not self._profile_path.exists():
            return {}
        try:
            data = json.loads(self._profile_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _write_profile(self) -> None:
        self._profile_path.parent.mkdir(parents=True, exist_ok=True)
        self._profile_path.write_text(json.dumps(self._profile, indent=2, sort_keys=True), encoding="utf-8")

    def _load_initial_state(self) -> PersonaState:
        requested_name = str(self._profile.get("persona", "") or "").strip() or DEFAULT_PERSONA
        try:
            return self._load_state(requested_name)
        except PersonaNotFoundError:
            # Fallback to default persona bundled with the project
            fallback = DEFAULT_PERSONA
            state = self._load_state(fallback)
            self._profile["persona"] = fallback
            self._write_profile()
            return state

    def _load_state(self, name: str) -> PersonaState:
        definition = load_persona(name)
        banned_words = [word for word in definition.banned_words if word.lower() != "none"]
        patterns = [re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE) for word in banned_words]
        return PersonaState(definition=definition, banned_word_patterns=patterns)

    # ------------------------------------------------------------------
    # Public API
    @property
    def current_name(self) -> str:
        return self._state.definition.name

    @property
    def current_definition(self) -> PersonaDefinition:
        return self._state.definition

    def list_personas(self) -> List[str]:
        return available_personas()

    def switch(self, name: str) -> PersonaDefinition:
        with self._lock:
            state = self._load_state(name)
            self._state = state
            self._profile["persona"] = name
            self._write_profile()
            return state.definition

    def reload(self) -> PersonaDefinition:
        with self._lock:
            self._state = self._load_state(self._state.definition.name)
            return self._state.definition

    def active_bundle(self) -> Tuple[PersonaDefinition, List[re.Pattern[str]]]:
        with self._lock:
            return self._state.definition, list(self._state.banned_word_patterns)

    def sanitize_response(
        self,
        message: str,
        *,
        patterns: Optional[List[re.Pattern[str]]] = None,
    ) -> str:
        sanitized = message
        active_patterns = patterns if patterns is not None else self._state.banned_word_patterns
        for pattern in active_patterns:
            sanitized = pattern.sub("[redacted]", sanitized)
        return sanitized

    def persona_preview(self) -> Dict[str, object]:
        definition = self._state.definition
        return {
            "persona": definition.name,
            "system_prompt": definition.system_prompt,
            "fewshots": len(definition.fewshots),
        }


_manager: Optional[PersonaManager] = None


def get_persona_manager() -> PersonaManager:
    global _manager
    if _manager is None:
        _manager = PersonaManager()
    return _manager


__all__ = ["PersonaManager", "get_persona_manager"]
