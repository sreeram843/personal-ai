from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class WorkflowRoleConfig:
    name: str
    instruction: str


DEFAULT_WORKFLOW_ROLES: Dict[str, WorkflowRoleConfig] = {
    "coordinator": WorkflowRoleConfig(
        name="coordinator",
        instruction=(
            "You are the coordinator. Break the user goal into a compact, dependency-aware task graph. "
            "Prefer the smallest useful plan. Use retriever for internal docs, researcher for fresh public context, "
            "synthesizer for the first answer draft, reviewer for critique, and writer for the final response."
        ),
    ),
    "retriever": WorkflowRoleConfig(
        name="retriever",
        instruction=(
            "You are the retrieval specialist. Ground the workflow in internal documents only. "
            "Return the most relevant evidence and avoid interpretation beyond short labels."
        ),
    ),
    "researcher": WorkflowRoleConfig(
        name="researcher",
        instruction=(
            "You are the fresh-context researcher. Search for recent public information only when needed. "
            "Prefer verifiable sources and preserve provenance."
        ),
    ),
    "synthesizer": WorkflowRoleConfig(
        name="synthesizer",
        instruction=(
            "You are the synthesizer. Build a strong draft from the shared evidence. "
            "If support is missing, say what cannot be verified instead of guessing."
        ),
    ),
    "reviewer": WorkflowRoleConfig(
        name="reviewer",
        instruction=(
            "You are the reviewer. Look for unsupported claims, weak structure, and missed constraints. "
            "Return concise revision notes only."
        ),
    ),
    "writer": WorkflowRoleConfig(
        name="writer",
        instruction=(
            "You are the writer. Produce the final user-facing answer using the reviewed draft and verified evidence. "
            "Keep it direct and avoid unsupported claims."
        ),
    ),
}


__all__ = ["WorkflowRoleConfig", "DEFAULT_WORKFLOW_ROLES"]