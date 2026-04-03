"""
Persona Manager Service

Loads and manages different personality/trait systems for the chatbot.
Supports runtime switching between different personas without model reloading.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PersonaManager:
    """Manages loading and switching between different personas/traits."""

    def __init__(self, personas_dir: Optional[str] = None):
        """
        Initialize PersonaManager.

        Args:
            personas_dir: Path to personas directory. Defaults to api/personas/
        """
        if personas_dir is None:
            # Default to api/personas relative to project root
            base_dir = Path(__file__).parent.parent.parent
            personas_dir = str(base_dir / "api" / "personas")

        self.personas_dir = Path(personas_dir)
        self._persona_cache: Dict[str, Dict[str, str]] = {}
        self._active_persona = "ideal_chatbot"

    def list_personas(self) -> list[str]:
        """List all available personas in the personas directory."""
        if not self.personas_dir.exists():
            return []

        personas = []
        for item in self.personas_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                personas.append(item.name)

        return sorted(personas)

    def load_persona(self, persona_name: str) -> Dict[str, str]:
        """
        Load a persona's files into a structured dictionary.

        Args:
            persona_name: Name of the persona (directory name)

        Returns:
            Dictionary with keys like 'identity', 'values', 'style', etc.
            and file contents as values.

        Raises:
            FileNotFoundError: If persona doesn't exist
        """
        if persona_name in self._persona_cache:
            return self._persona_cache[persona_name]

        persona_path = self.personas_dir / persona_name
        if not persona_path.exists():
            raise FileNotFoundError(f"Persona '{persona_name}' not found")

        persona_data = {}

        # Define the files we expect in a persona directory
        file_mappings = {
            "identity": "00_identity.md",
            "values": "01_values.md",
            "decision_rules": "02_decision_rules.md",
            "style": "03_style.md",
            "emotion_rules": "04_emotion_rules.md",
            "negative_examples": "06_negative_examples.md",
            "glossary": "07_glossary.md",
        }

        # Load markdown files
        for key, filename in file_mappings.items():
            filepath = persona_path / filename
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        persona_data[key] = f.read()
                    logger.debug(f"Loaded {key} from {persona_name}")
                except Exception as e:
                    logger.warning(f"Failed to load {filename} from {persona_name}: {e}")

        # Load few-shots (JSONL)
        fewshots_path = persona_path / "08_fewshots.jsonl"
        if fewshots_path.exists():
            try:
                with open(fewshots_path, "r", encoding="utf-8") as f:
                    persona_data["fewshots"] = f.read()
                logger.debug(f"Loaded fewshots from {persona_name}")
            except Exception as e:
                logger.warning(f"Failed to load fewshots from {persona_name}: {e}")

        # Load rubrics (directory)
        rubrics_dir = persona_path / "05_rubrics"
        if rubrics_dir.exists():
            rubrics = {}
            for rubric_file in rubrics_dir.glob("*.md"):
                try:
                    with open(rubric_file, "r", encoding="utf-8") as f:
                        rubric_name = rubric_file.stem
                        rubrics[rubric_name] = f.read()
                    logger.debug(f"Loaded rubric {rubric_name} from {persona_name}")
                except Exception as e:
                    logger.warning(f"Failed to load rubric {rubric_file.name}: {e}")
            if rubrics:
                persona_data["rubrics"] = rubrics

        self._persona_cache[persona_name] = persona_data
        return persona_data

    def get_persona_system_prompt(self, persona_name: str) -> str:
        """
        Generate a system prompt from a loaded persona.

        Args:
            persona_name: Name of the persona to load

        Returns:
            System prompt string combining persona files
        """
        persona = self.load_persona(persona_name)

        sections = []

        # Build prompt from persona components
        if "identity" in persona:
            sections.append("## Identity\n" + persona["identity"])

        if "values" in persona:
            sections.append("## Values & Principles\n" + persona["values"])

        if "decision_rules" in persona:
            sections.append("## Decision Rules\n" + persona["decision_rules"])

        if "style" in persona:
            sections.append("## Communication Style\n" + persona["style"])

        if "emotion_rules" in persona:
            sections.append("## Emotional Responses\n" + persona["emotion_rules"])

        if "glossary" in persona:
            sections.append("## Preferred Terminology\n" + persona["glossary"])

        if "negative_examples" in persona:
            sections.append("## Behaviors to Avoid\n" + persona["negative_examples"])

        # Optionally include rubrics
        if "rubrics" in persona:
            sections.append("## Evaluation Rubrics\n")
            for rubric_name, rubric_content in persona["rubrics"].items():
                sections.append(f"### {rubric_name}\n{rubric_content}")

        system_prompt = "\n\n".join(sections)
        return system_prompt

    def set_active_persona(self, persona_name: str) -> None:
        """
        Set the currently active persona.

        Args:
            persona_name: Name of the persona to activate
        """
        if persona_name not in self.list_personas():
            raise ValueError(f"Unknown persona: {persona_name}")
        self._active_persona = persona_name

    def get_active_persona(self) -> str:
        """Get the name of the currently active persona."""
        return self._active_persona

    def get_active_system_prompt(self) -> str:
        """Get the system prompt for the currently active persona."""
        return self.get_persona_system_prompt(self._active_persona)

    def reload_persona_cache(self) -> None:
        """Clear the persona cache (forces reload from disk on next access)."""
        self._persona_cache.clear()
        logger.info("Persona cache cleared")
