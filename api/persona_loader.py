from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

PERSONA_ROOT = Path(__file__).resolve().parent / "personas"


@dataclass(frozen=True)
class PersonaDefinition:
    """Materialized persona assets ready for prompt construction."""

    name: str
    system_prompt: str
    fewshots: List[Dict[str, str]]
    banned_words: List[str]


class PersonaNotFoundError(FileNotFoundError):
    """Raised when the persona directory is missing."""


def available_personas() -> List[str]:
    """Return sorted list of persona directory names."""

    if not PERSONA_ROOT.exists():
        return []
    return sorted([p.name for p in PERSONA_ROOT.iterdir() if p.is_dir()])


def _read_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _parse_banned_words(style_text: str) -> List[str]:
    match = re.search(r"Banned words:\s*(.+)", style_text, re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1)
    # Remove trailing punctuation and split on commas
    words = []
    for chunk in raw.split(","):
        cleaned = re.sub(r"[“”\"']", "", chunk).strip().strip(".")
        if cleaned:
            words.append(cleaned.lower())
    return words


def _collect_rubrics(path: Path) -> Iterable[str]:
    rubrics_dir = path / "05_rubrics"
    if not rubrics_dir.is_dir():
        return []
    sections: List[str] = []
    for file in sorted(rubrics_dir.glob("*.md")):
        title = file.stem.replace("_", " ").title()
        sections.append(f"Rubric — {title}\n{_read_text(file)}")
    return sections


def _load_fewshots(path: Path) -> List[Dict[str, str]]:
    fewshots_path = path / "08_fewshots.jsonl"
    if not fewshots_path.exists():
        return []

    fewshots: List[Dict[str, str]] = []
    for raw_line in fewshots_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        data = json.loads(line)
        if not isinstance(data, dict) or "role" not in data or "content" not in data:
            raise ValueError(f"Invalid fewshot entry: {line}")
        fewshots.append({"role": str(data["role"]), "content": str(data["content"])})
    return fewshots


def load_persona(name: str) -> PersonaDefinition:
    """Load persona definition by name, composing system prompt and fewshots."""

    persona_path = PERSONA_ROOT / name
    if not persona_path.is_dir():
        raise PersonaNotFoundError(f"Persona '{name}' not found in {PERSONA_ROOT}")

    sections: List[str] = []

    identity = _read_text(persona_path / "00_identity.md")
    if identity:
        sections.append(identity)

    values = _read_text(persona_path / "01_values.md")
    if values:
        sections.append(values)

    decisions = _read_text(persona_path / "02_decision_rules.md")
    if decisions:
        sections.append("Decision Rules:\n" + decisions)

    style = _read_text(persona_path / "03_style.md")
    banned_words = _parse_banned_words(style)
    if style:
        sections.append("Style Guide:\n" + style)

    emotion = _read_text(persona_path / "04_emotion_rules.md")
    if emotion:
        sections.append("Emotion Rules:\n" + emotion)

    sections.extend(_collect_rubrics(persona_path))

    negatives = _read_text(persona_path / "06_negative_examples.md")
    if negatives:
        sections.append("Negative Examples:\n" + negatives)

    glossary = _read_text(persona_path / "07_glossary.md")
    if glossary:
        sections.append("Glossary:\n" + glossary)

    # Guarantee the safety disclaimer exists verbatim for downstream validation/tests.
    joined_preview = "\n\n".join(section.strip() for section in sections if section).strip()
    if "not legal advice" not in joined_preview.lower():
        sections.append("Reminder: This guidance is not legal advice.")

    system_prompt = "\n\n".join(section.strip() for section in sections if section).strip()

    fewshots = _load_fewshots(persona_path)

    return PersonaDefinition(
        name=name,
        system_prompt=system_prompt,
        fewshots=fewshots,
        banned_words=banned_words,
    )


__all__ = [
    "PersonaDefinition",
    "PersonaNotFoundError",
    "available_personas",
    "load_persona",
]
