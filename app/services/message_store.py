"""
Agent message store for inbox/outbox persistence.

Manages per-run message queues and event streams for inter-agent communication,
persisting handoffs, messages, and communication events.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas.message import AgentMessage, HandoffSummary, MessageEvent, MessageType


logger = logging.getLogger(__name__)


class AgentMessageStore:
    """Manages agent messages, inbox/outbox, and event streams."""

    def __init__(self, storage_path: str = "memory/messages"):
        """Initialize message store."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._inboxes: Dict[str, List[AgentMessage]] = {}
        self._outboxes: Dict[str, List[AgentMessage]] = {}
        self._handoffs: Dict[str, List[HandoffSummary]] = {}
        self._events: Dict[str, List[MessageEvent]] = {}

    def add_message(self, message: AgentMessage) -> None:
        """
        Add a message to the appropriate agent's inbox.

        Args:
            message: AgentMessage to store
        """
        run_id = message.run_id
        agent = message.to_agent

        # Add to inbox
        inbox_key = f"{run_id}:{agent}"
        if inbox_key not in self._inboxes:
            self._inboxes[inbox_key] = []
        self._inboxes[inbox_key].append(message)

        # Persist
        self._persist_message(message)

    def get_inbox(self, run_id: str, agent: str) -> List[AgentMessage]:
        """
        Get all messages in agent's inbox for a run.

        Args:
            run_id: Workflow run ID
            agent: Agent name

        Returns:
            List of messages in agent's inbox
        """
        inbox_key = f"{run_id}:{agent}"
        if inbox_key not in self._inboxes:
            self._load_inbox(run_id, agent)
        return self._inboxes.get(inbox_key, [])

    def mark_message_read(self, message_id: str) -> None:
        """Mark a message as read (simple flag)."""
        # For now, just log - could add read_at timestamp to message
        logger.debug(f"Marked message {message_id} as read")

    def add_handoff(self, handoff: HandoffSummary, run_id: str) -> None:
        """
        Record a handoff between agents.

        Args:
            handoff: HandoffSummary with transition details
            run_id: Workflow run ID
        """
        if run_id not in self._handoffs:
            self._handoffs[run_id] = []
        self._handoffs[run_id].append(handoff)

        # Create handoff event
        event = MessageEvent(
            type="handoff_complete",
            run_id=run_id,
            step_id=handoff.step_id,
            agent=f"{handoff.from_agent} -> {handoff.to_agent}",
            data={
                "from_agent": handoff.from_agent,
                "to_agent": handoff.to_agent,
                "summary": handoff.summary[:200],
                "evidence_count": handoff.evidence_count,
                "confidence": handoff.confidence,
            },
        )
        self.add_event(event)

        # Persist
        self._persist_handoff(run_id, handoff)

    def get_handoffs(self, run_id: str) -> List[HandoffSummary]:
        """Get all handoffs for a run."""
        if run_id not in self._handoffs:
            self._load_handoffs(run_id)
        return self._handoffs.get(run_id, [])

    def add_event(self, event: MessageEvent) -> None:
        """
        Add event to stream.

        Args:
            event: MessageEvent to record
        """
        run_id = event.run_id
        if run_id not in self._events:
            self._events[run_id] = []
        self._events[run_id].append(event)

        # Persist
        self._persist_event(run_id, event)

    def get_events(self, run_id: str, since: Optional[datetime] = None) -> List[MessageEvent]:
        """
        Get events for a run, optionally filtered by timestamp.

        Args:
            run_id: Workflow run ID
            since: Optional datetime to filter events after

        Returns:
            List of events
        """
        if run_id not in self._events:
            self._load_events(run_id)

        events = self._events.get(run_id, [])
        if since:
            events = [e for e in events if e.timestamp >= since]
        return events

    def get_communication_summary(self, run_id: str) -> Dict:
        """
        Get summary of all communication for a run.

        Args:
            run_id: Workflow run ID

        Returns:
            Summary dict with message counts, handoffs, key events
        """
        messages = []
        for key, msgs in self._inboxes.items():
            if key.startswith(run_id):
                messages.extend(msgs)

        handoffs = self.get_handoffs(run_id)
        events = self.get_events(run_id)

        message_types = {}
        for msg in messages:
            msg_type = msg.type.value
            message_types[msg_type] = message_types.get(msg_type, 0) + 1

        return {
            "message_count": len(messages),
            "message_types": message_types,
            "handoff_count": len(handoffs),
            "handoffs": [
                {
                    "from": h.from_agent,
                    "to": h.to_agent,
                    "step": h.step_id,
                    "confidence": h.confidence,
                }
                for h in handoffs
            ],
            "event_count": len(events),
            "key_events": [
                {
                    "type": e.type,
                    "timestamp": e.timestamp.isoformat(),
                    "severity": e.severity,
                }
                for e in events[-10:]  # Last 10 events
            ],
        }

    def _persist_message(self, message: AgentMessage) -> None:
        """Persist message to disk."""
        run_dir = self.storage_path / message.run_id / "messages"
        run_dir.mkdir(parents=True, exist_ok=True)

        msg_file = run_dir / f"{message.id}.json"
        with open(msg_file, "w") as f:
            json.dump(message.model_dump(mode="json"), f, default=str)

    def _load_inbox(self, run_id: str, agent: str) -> None:
        """Load inbox messages from disk."""
        inbox_key = f"{run_id}:{agent}"
        messages_dir = self.storage_path / run_id / "messages"

        if not messages_dir.exists():
            self._inboxes[inbox_key] = []
            return

        messages = []
        for msg_file in messages_dir.glob("*.json"):
            try:
                with open(msg_file) as f:
                    data = json.load(f)
                    msg = AgentMessage(**data)
                    if msg.to_agent == agent:
                        messages.append(msg)
            except Exception as e:
                logger.error(f"Error loading message {msg_file}: {e}")

        self._inboxes[inbox_key] = messages

    def _persist_handoff(self, run_id: str, handoff: HandoffSummary) -> None:
        """Persist handoff summary to disk."""
        handoff_file = self.storage_path / run_id / "handoffs.jsonl"
        handoff_file.parent.mkdir(parents=True, exist_ok=True)

        with open(handoff_file, "a") as f:
            f.write(handoff.model_dump_json() + "\n")

    def _load_handoffs(self, run_id: str) -> None:
        """Load handoff summaries from disk."""
        handoff_file = self.storage_path / run_id / "handoffs.jsonl"

        handoffs = []
        if handoff_file.exists():
            try:
                with open(handoff_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            handoff = HandoffSummary(**data)
                            handoffs.append(handoff)
            except Exception as e:
                logger.error(f"Error loading handoffs for {run_id}: {e}")

        self._handoffs[run_id] = handoffs

    def _persist_event(self, run_id: str, event: MessageEvent) -> None:
        """Persist event to disk."""
        event_file = self.storage_path / run_id / "events.jsonl"
        event_file.parent.mkdir(parents=True, exist_ok=True)

        with open(event_file, "a") as f:
            data = json.loads(event.model_dump_json())
            f.write(json.dumps(data, default=str) + "\n")

    def _load_events(self, run_id: str) -> None:
        """Load events from disk."""
        event_file = self.storage_path / run_id / "events.jsonl"

        events = []
        if event_file.exists():
            try:
                with open(event_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            event = MessageEvent(**data)
                            events.append(event)
            except Exception as e:
                logger.error(f"Error loading events for {run_id}: {e}")

        self._events[run_id] = events
