from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class PersonaSwitchRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PersonaInfo(BaseModel):
    persona: str


class PersonaPreview(BaseModel):
    persona: str
    system_prompt: str
    fewshots: int


class PersonaList(BaseModel):
    personas: List[str]


__all__ = [
    "PersonaSwitchRequest",
    "PersonaInfo",
    "PersonaPreview",
    "PersonaList",
]
