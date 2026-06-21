"""Tests for system prompt loading."""

from app.services.system_prompt import get_system_prompt


def test_system_prompt_loads_from_default_file():
    prompt = get_system_prompt()
    assert "principled, user-centric assistant" in prompt
    assert "Core Traits" in prompt
    assert len(prompt) > 500
