"""Agent Lab, Phase 6a: an agent that forms durable memory from a conversation.

This is the hardest practical problem in agents: what's worth remembering,
and how do you recall it later without just dumping the whole history back
in? Here that's split into two deliberately separate pieces:

  1. Extraction — an LLM reads a transcript and pulls out durable facts
     (preferences, goals, identity), skipping anything transient.
  2. Recall — a plain string block built from stored facts, meant to be
     prepended to another agent's system prompt in a later session.

Storage is a small disk-backed store separate from the production
app/services/user_memory.py, so this phase is safe to experiment on without
touching real user data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.services.learn_agents._llm_client import chat_completion, extract_message
from app.services.learn_agents.tracing import RunTrace

EXTRACT_SYSTEM_PROMPT = (
    "You extract durable facts worth remembering across future conversations from a "
    "chat transcript: user preferences, stated goals, ongoing projects, identity details. "
    "Skip anything transient (a one-off question, small talk). Reply with ONLY a JSON "
    'array of short strings, e.g. ["Prefers concise answers", "Building a Python CLI tool"]. '
    "If nothing is worth remembering, reply with []."
)

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_facts(text: str) -> List[str]:
    match = _JSON_ARRAY_RE.search(text)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if str(item).strip()][:10]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LabMemoryStore:
    """Disk-backed, per-user durable facts — lab-only, separate from production memory."""

    def __init__(self, file_path: str = "memory/agent_lab/facts.json") -> None:
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except json.JSONDecodeError:
            return {}

    def _write_all(self, data: Dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, indent=2))

    def add_facts(self, user_id: str, facts: List[str]) -> None:
        if not user_id or not facts:
            return
        data = self._read_all()
        bucket = data.setdefault(user_id, {"facts": [], "updated_at": _utc_now()})
        existing: List[str] = bucket.setdefault("facts", [])
        for fact in facts:
            if fact not in existing:
                existing.append(fact)
        bucket["facts"] = existing[-30:]
        bucket["updated_at"] = _utc_now()
        self._write_all(data)

    def get_facts(self, user_id: str) -> List[str]:
        data = self._read_all()
        return list((data.get(user_id) or {}).get("facts") or [])

    def get_recall_block(self, user_id: str, *, limit: int = 5) -> str:
        facts = self.get_facts(user_id)
        if not facts:
            return ""
        recent = facts[-limit:]
        return "Known about this user:\n" + "\n".join(f"- {fact}" for fact in recent)


_default_store: Optional[LabMemoryStore] = None


def get_lab_memory_store() -> LabMemoryStore:
    global _default_store
    if _default_store is None:
        _default_store = LabMemoryStore()
    return _default_store


@dataclass
class MemoryAgentResult:
    facts: List[str]
    recall_block: str


async def run_memory_agent(
    *,
    user_id: str,
    turns: List[Dict[str, str]],
    settings: Settings,
    store: LabMemoryStore,
    trace: Optional[RunTrace] = None,
) -> MemoryAgentResult:
    transcript = "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in turns)
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Transcript:\n{transcript}"},
    ]
    if trace is not None:
        with trace.llm_call(request={"messages": messages}) as recorder:
            _, raw = await chat_completion(messages=messages, settings=settings)
            recorder.response = raw
    else:
        _, raw = await chat_completion(messages=messages, settings=settings)

    text = str(extract_message(raw).get("content") or "")
    facts = _parse_facts(text)
    store.add_facts(user_id, facts)
    recall_block = store.get_recall_block(user_id)

    if trace is not None:
        trace.finish(answer=recall_block or "(no durable facts extracted)", steps=1)

    return MemoryAgentResult(facts=facts, recall_block=recall_block)


__all__ = [
    "run_memory_agent",
    "MemoryAgentResult",
    "LabMemoryStore",
    "get_lab_memory_store",
]
