"""Tests for PersonaManager service"""

import pytest
from app.services.persona_manager import PersonaManager


def test_persona_manager_lists_personas():
    """Test that PersonaManager can list all available personas"""
    manager = PersonaManager()
    personas = manager.list_personas()
    
    # Should have at least 3 personas
    assert len(personas) >= 3
    assert "ideal_chatbot" in personas
    assert "therapist" in personas
    assert "barney" in personas


def test_persona_manager_loads_persona():
    """Test that PersonaManager can load a persona's files"""
    manager = PersonaManager()
    persona = manager.load_persona("ideal_chatbot")
    
    # Should have key files loaded
    assert "identity" in persona
    assert "values" in persona
    assert "decision_rules" in persona
    assert "style" in persona


def test_persona_manager_generates_system_prompt():
    """Test that PersonaManager generates a system prompt for a persona"""
    manager = PersonaManager()
    prompt = manager.get_persona_system_prompt("ideal_chatbot")
    
    # Prompt should be substantial
    assert len(prompt) > 1000
    # Should contain key sections
    assert "Identity" in prompt
    assert "Values" in prompt


def test_persona_manager_switching():
    """Test persona switching"""
    manager = PersonaManager()
    
    # Start with default
    assert manager.get_active_persona() == "ideal_chatbot"
    
    # Switch to therapist
    manager.set_active_persona("therapist")
    assert manager.get_active_persona() == "therapist"
    
    # Switch to barney
    manager.set_active_persona("barney")
    assert manager.get_active_persona() == "barney"


def test_persona_manager_invalid_persona():
    """Test that switching to invalid persona raises error"""
    manager = PersonaManager()
    
    with pytest.raises(ValueError):
        manager.set_active_persona("nonexistent_persona")


def test_persona_manager_caching():
    """Test that personas are cached after first load"""
    manager = PersonaManager()
    
    # First load
    persona1 = manager.load_persona("ideal_chatbot")
    
    # Second load should be from cache
    persona2 = manager.load_persona("ideal_chatbot")
    
    # Should be the same object (not just equal)
    assert persona1 is persona2


def test_persona_manager_cache_reload():
    """Test that cache can be cleared"""
    manager = PersonaManager()
    
    # Load a persona
    manager.load_persona("ideal_chatbot")
    
    # Clear cache
    manager.reload_persona_cache()
    
    # Load again (should reload from disk)
    persona = manager.load_persona("ideal_chatbot")
    assert persona is not None
    assert "identity" in persona
