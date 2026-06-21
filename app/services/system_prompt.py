from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system.md"


@lru_cache
def get_system_prompt() -> str:
    """Load the assistant system prompt from disk (cached)."""
    settings = get_settings()
    path = Path(settings.system_prompt_path) if settings.system_prompt_path else _DEFAULT_PROMPT_PATH
    if not path.is_file():
        raise FileNotFoundError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
