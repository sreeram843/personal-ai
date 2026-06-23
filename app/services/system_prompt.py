from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system.md"
_DEFAULT_DEMO_CONTEXT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "demo-about.md"
_DEFAULT_DEMO_CRICKET_PATH = Path(__file__).resolve().parent.parent / "prompts" / "demo-cricket.md"

_DEMO_PROFESSIONAL_SHARE = 0.85

_DEMO_SPORT_SEPARATOR = "\n\n<<<DEMO_CRICKET_PROFILE>>>\n\n"
_PROFESSIONAL_TRUNCATION_MARKER = (
    "\n\n[... additional professional details omitted for demo context limit ...]\n\n"
)
_SPORT_TRUNCATION_MARKER = "\n\n[... additional cricket details omitted for demo context limit ...]\n\n"

_DEMO_TRAITS = (
    "You are CurAI on Sriram Mentey's portfolio demo. "
    "Be concise, accurate, and friendly. "
    "Answer using only the profile below; if a fact is missing, say so — do not guess. "
    "Speak in third person about Sriram. "
    "Lead with the answer; keep replies interview-friendly unless the visitor asks for depth."
)

_DEMO_PREFIX = (
    f"{_DEMO_TRAITS}\n\n"
    "---\n\n"
    "## Portfolio demo mode\n\n"
    "The visitor is trying the embeddable portfolio demo. Prioritize accurate answers about "
    "Sriram Mentey's professional background, education, and projects from the profile below. "
    "Sport/cricket details are secondary unless the visitor asks about cricket.\n\n"
)


@lru_cache
def get_system_prompt() -> str:
    """Load the assistant system prompt from disk (cached)."""
    settings = get_settings()
    path = Path(settings.system_prompt_path) if settings.system_prompt_path else _DEFAULT_PROMPT_PATH
    if not path.is_file():
        raise FileNotFoundError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _truncate_head(text: str, max_chars: int, *, marker: str) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if len(marker) >= max_chars:
        return text[:max_chars]
    keep = max_chars - len(marker)
    return f"{text[:keep].rstrip()}{marker}"


def _build_demo_knowledge_prompt(*, profile: str, cricket: str, max_chars: int) -> str:
    """Assemble demo knowledge with a fixed 85% professional / 15% sport budget."""
    if len(_DEMO_PREFIX) >= max_chars:
        return _DEMO_PREFIX[:max_chars]

    knowledge_budget = max_chars - len(_DEMO_PREFIX)
    professional_budget = max(int(knowledge_budget * _DEMO_PROFESSIONAL_SHARE), 1)
    sport_budget = max(knowledge_budget - professional_budget, 0)

    professional_block = _truncate_head(
        profile.strip(),
        professional_budget,
        marker=_PROFESSIONAL_TRUNCATION_MARKER,
    )

    sport_block = ""
    cricket_text = cricket.strip()
    separator_len = len(_DEMO_SPORT_SEPARATOR)
    if cricket_text and sport_budget > separator_len:
        cricket_allowance = sport_budget - separator_len
        cricket_block = _truncate_head(
            cricket_text,
            cricket_allowance,
            marker=_SPORT_TRUNCATION_MARKER,
        )
        if cricket_block:
            sport_block = f"{_DEMO_SPORT_SEPARATOR}{cricket_block}"

    prompt = f"{_DEMO_PREFIX}{professional_block}{sport_block}"
    if len(prompt) > max_chars:
        return prompt[:max_chars]
    return prompt


@lru_cache
def get_demo_system_prompt() -> str:
    """Portfolio demo prompt: compact traits plus Sriram's public profile."""
    settings = get_settings()
    context_path = Path(settings.demo_context_path) if settings.demo_context_path else _DEFAULT_DEMO_CONTEXT_PATH
    if not context_path.is_file():
        raise FileNotFoundError(f"Demo context not found: {context_path}")

    profile = context_path.read_text(encoding="utf-8").strip()
    cricket = ""
    if _DEFAULT_DEMO_CRICKET_PATH.is_file():
        cricket = _DEFAULT_DEMO_CRICKET_PATH.read_text(encoding="utf-8").strip()

    return _build_demo_knowledge_prompt(
        profile=profile,
        cricket=cricket,
        max_chars=settings.demo_context_max_chars,
    )
