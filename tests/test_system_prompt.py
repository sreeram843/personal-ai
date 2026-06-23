"""Tests for system prompt loading."""

from app.core.config import Settings, get_settings
from app.services import system_prompt as system_prompt_module
from app.services.system_prompt import (
    _DEMO_PREFIX,
    _DEMO_SPORT_SEPARATOR,
    _build_demo_knowledge_prompt,
    get_demo_system_prompt,
    get_system_prompt,
)


def test_system_prompt_loads_from_default_file():
    prompt = get_system_prompt()
    assert "principled, user-centric assistant" in prompt
    assert "Core Traits" in prompt
    assert len(prompt) > 500


def _split_demo_knowledge(prompt: str) -> tuple[str, str]:
    knowledge = prompt[len(_DEMO_PREFIX) :]
    sport_idx = knowledge.find(_DEMO_SPORT_SEPARATOR)
    if sport_idx < 0:
        return knowledge.strip(), ""
    return knowledge[:sport_idx].strip(), knowledge[sport_idx + len(_DEMO_SPORT_SEPARATOR) :].strip()


def test_demo_system_prompt_includes_profile():
    system_prompt_module.get_demo_system_prompt.cache_clear()
    prompt = get_demo_system_prompt()
    assert "Sriram Mentey" in prompt
    assert "Teladoc Health" in prompt
    assert "Cricket" in prompt
    assert "1259840" in prompt
    assert "github.com/sreeram843" in prompt
    assert "medium.com/@menteysriram43" in prompt
    assert "portfolio demo" in prompt.lower()
    assert len(prompt) <= get_settings().demo_context_max_chars


def test_demo_system_prompt_professional_dominates_cricket():
    system_prompt_module.get_demo_system_prompt.cache_clear()
    prompt = get_demo_system_prompt()
    professional, sport = _split_demo_knowledge(prompt)
    assert professional
    assert sport
    total = len(professional) + len(sport)
    professional_share = len(professional) / total
    assert professional_share >= 0.84
    assert professional_share <= 0.86


def test_demo_system_prompt_truncates_when_budget_exceeded(monkeypatch):
    system_prompt_module.get_demo_system_prompt.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(
        system_prompt_module,
        "get_settings",
        lambda: Settings(**{**settings.model_dump(), "demo_context_max_chars": 1200}),
    )
    prompt = get_demo_system_prompt()
    assert len(prompt) <= 1200
    assert "professional details omitted" in prompt or "cricket details omitted" in prompt


def test_build_demo_knowledge_prompt_enforces_ratio():
    profile = "PROF " * 2000
    cricket = "# Cricket profile\n\n" + ("SPORT " * 500)
    prompt = _build_demo_knowledge_prompt(profile=profile, cricket=cricket, max_chars=4000)
    professional, sport = _split_demo_knowledge(prompt)
    total = len(professional) + len(sport)
    assert total > 0
    assert abs((len(professional) / total) - 0.85) < 0.03
    assert sport.startswith("# Cricket profile")
