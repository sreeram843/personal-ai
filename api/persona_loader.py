"""
Persona Loader Utilities

Utilities for loading and managing persona files from the api/personas directory.
"""

import json
from pathlib import Path
from typing import Optional


def load_persona_directory(persona_name: str, personas_base_dir: Optional[str] = None) -> dict:
    """
    Load all files from a persona directory.

    Args:
        persona_name: Name of the persona (directory name under personas/)
        personas_base_dir: Base directory containing personas. Defaults to api/personas/

    Returns:
        Dictionary with persona file contents
    """
    if personas_base_dir is None:
        base_dir = Path(__file__).parent.parent.parent
        personas_base_dir = str(base_dir / "api" / "personas")

    persona_path = Path(personas_base_dir) / persona_name

    if not persona_path.exists():
        raise FileNotFoundError(f"Persona directory not found: {persona_path}")

    persona_files = {}

    # Load text files
    for md_file in persona_path.glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            key = md_file.stem  # Filename without extension
            persona_files[key] = f.read()

    # Load JSONL fewshots
    fewshots_file = persona_path / "08_fewshots.jsonl"
    if fewshots_file.exists():
        examples = []
        with open(fewshots_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))
        persona_files["fewshots_examples"] = examples

    # Load rubrics
    rubrics_dir = persona_path / "05_rubrics"
    if rubrics_dir.exists():
        persona_files["rubrics"] = {}
        for rubric_file in rubrics_dir.glob("*.md"):
            with open(rubric_file, "r", encoding="utf-8") as f:
                persona_files["rubrics"][rubric_file.stem] = f.read()

    return persona_files


def merge_personas(*persona_names: str, personas_base_dir: Optional[str] = None) -> str:
    """
    Load and merge multiple personas into a single system prompt.
    Later personas override earlier ones in case of conflicts.

    Args:
        persona_names: Names of personas to merge
        personas_base_dir: Base directory containing personas

    Returns:
        Merged system prompt string
    """
    sections = []

    for persona_name in persona_names:
        persona_data = load_persona_directory(persona_name, personas_base_dir)

        # Add identity
        if "00_identity" in persona_data:
            sections.append(f"## {persona_name.title()} - Identity\n{persona_data['00_identity']}\n")

        # Add values
        if "01_values" in persona_data:
            sections.append(f"## {persona_name.title()} - Values\n{persona_data['01_values']}\n")

        # Add decision rules
        if "02_decision_rules" in persona_data:
            sections.append(f"## {persona_name.title()} - Decision Rules\n{persona_data['02_decision_rules']}\n")

        # Add style
        if "03_style" in persona_data:
            sections.append(f"## {persona_name.title()} - Style\n{persona_data['03_style']}\n")

    return "\n---\n".join(sections)
