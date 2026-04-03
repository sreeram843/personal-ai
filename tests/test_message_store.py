"""Tests for agent communication and message store."""

import json
import tempfile
from pathlib import Path

import pytest

from app.schemas.message import (
    AgentMessage,
    Evidence,
    EvidenceType,
    HandoffSummary,
    MessageEvent,
    MessageType,
)
from app.services.message_store import AgentMessageStore


class TestAgentMessages:
    """Basic agent message tests."""

    def test_evidence_is_immutable(self):
        """Evidence should be immutable once created."""
        evidence = Evidence(
            type=EvidenceType.CONTEXT,
            source_agent="retriever",
            content="Retrieved context",
        )
        
        # Check immutability
        with pytest.raises(Exception):  # Should raise validation error
            evidence.content = "Modified"

    def test_agent_message_creation(self):
        """Agent messages should have all required fields."""
        msg = AgentMessage(
            type=MessageType.HANDOFF,
            from_agent="researcher",
            to_agent="synthesizer",
            conversation_id="conv_123",
            run_id="run_456",
            subject="Research complete",
            body="Found 5 relevant sources",
        )
        
        assert msg.id is not None
        assert msg.created_at is not None
        assert msg.from_agent == "researcher"
        assert msg.to_agent == "synthesizer"

    def test_evidence_with_confidence(self):
        """Evidence should track confidence scores."""
        evidence = Evidence(
            type=EvidenceType.DRAFT,
            source_agent="synthesizer",
            content="Draft answer",
            confidence=0.85,
        )
        
        assert evidence.confidence == 0.85
        assert evidence.id is not None

    def test_handoff_summary_creation(self):
        """Handoff summaries should capture agent transitions."""
        handoff = HandoffSummary(
            from_agent="retriever",
            to_agent="synthesizer",
            step_id="retrieve_context",
            summary="Found 10 documents relevant to query",
            key_decisions=["Used BM25 ranking", "Limited to 10 results"],
            evidence_count=10,
            confidence=0.9,
        )
        
        assert handoff.from_agent == "retriever"
        assert handoff.to_agent == "synthesizer"
        assert len(handoff.key_decisions) == 2
        assert handoff.confidence == 0.9


class TestMessageStore:
    """Message store persistence tests."""

    @pytest.fixture
    def store(self):
        """Create temporary message store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield AgentMessageStore(storage_path=tmpdir)

    def test_message_store_adds_message(self, store):
        """Store should add and retrieve messages."""
        msg = AgentMessage(
            type=MessageType.HANDOFF,
            from_agent="retriever",
            to_agent="synthesizer",
            conversation_id="conv_123",
            run_id="run_456",
            subject="Context ready",
            body="Retrieved 5 documents",
        )
        
        store.add_message(msg)
        inbox = store.get_inbox("run_456", "synthesizer")
        
        assert len(inbox) == 1
        assert inbox[0].from_agent == "retriever"
        assert inbox[0].subject == "Context ready"

    def test_message_store_filters_by_recipient(self, store):
        """Store should only return messages for specific agents."""
        msg1 = AgentMessage(
            type=MessageType.HANDOFF,
            from_agent="retriever",
            to_agent="synthesizer",
            conversation_id="conv_123",
            run_id="run_456",
            subject="Message 1",
            body="For synthesizer",
        )
        
        msg2 = AgentMessage(
            type=MessageType.HANDOFF,
            from_agent="synthesizer",
            to_agent="reviewer",
            conversation_id="conv_123",
            run_id="run_456",
            subject="Message 2",
            body="For reviewer",
        )
        
        store.add_message(msg1)
        store.add_message(msg2)
        
        synthesizer_inbox = store.get_inbox("run_456", "synthesizer")
        reviewer_inbox = store.get_inbox("run_456", "reviewer")
        
        assert len(synthesizer_inbox) == 1
        assert len(reviewer_inbox) == 1
        assert synthesizer_inbox[0].subject == "Message 1"
        assert reviewer_inbox[0].subject == "Message 2"

    def test_message_with_evidence(self, store):
        """Messages should carry evidence artifacts."""
        evidence1 = Evidence(
            type=EvidenceType.CONTEXT,
            source_agent="retriever",
            content="Document 1 content",
            confidence=0.9,
        )
        
        evidence2 = Evidence(
            type=EvidenceType.CONTEXT,
            source_agent="retriever",
            content="Document 2 content",
            confidence=0.85,
        )
        
        msg = AgentMessage(
            type=MessageType.HANDOFF,
            from_agent="retriever",
            to_agent="synthesizer",
            conversation_id="conv_123",
            run_id="run_456",
            subject="Context with evidence",
            body="See evidence",
            evidence=[evidence1, evidence2],
        )
        
        store.add_message(msg)
        inbox = store.get_inbox("run_456", "synthesizer")
        
        assert len(inbox[0].evidence) == 2
        assert inbox[0].evidence[0].confidence == 0.9

    def test_handoff_persistence(self, store):
        """Handoffs should persist to disk."""
        handoff = HandoffSummary(
            from_agent="retriever",
            to_agent="synthesizer",
            step_id="retrieve_context",
            summary="Retrieved context",
            evidence_count=5,
        )
        
        store.add_handoff(handoff, "run_456")
        
        # Verify event was created
        events = store.get_events("run_456")
        assert any(e.type == "handoff_complete" for e in events)
        
        # Verify handoff retrieval
        handoffs = store.get_handoffs("run_456")
        assert len(handoffs) == 1
        assert handoffs[0].from_agent == "retriever"

    def test_message_events(self, store):
        """Store should track message events."""
        event1 = MessageEvent(
            type="message_received",
            run_id="run_456",
            agent="synthesizer",
            data={"from": "retriever", "subject": "Context ready"},
        )
        
        event2 = MessageEvent(
            type="message_processed",
            run_id="run_456",
            agent="synthesizer",
            data={"action": "draft_created"},
        )
        
        store.add_event(event1)
        store.add_event(event2)
        
        events = store.get_events("run_456")
        assert len(events) >= 2  # May have handoff event from above
        assert any(e.type == "message_received" for e in events)
        assert any(e.type == "message_processed" for e in events)

    def test_communication_summary(self, store):
        """Store should provide communication summary."""
        # Add several messages and handoffs
        msg = AgentMessage(
            type=MessageType.HANDOFF,
            from_agent="retriever",
            to_agent="synthesizer",
            conversation_id="conv_123",
            run_id="run_456",
            subject="Ready",
            body="Context retrieved",
        )
        
        handoff = HandoffSummary(
            from_agent="retriever",
            to_agent="synthesizer",
            step_id="step_1",
            summary="Handed off context",
            evidence_count=3,
        )
        
        store.add_message(msg)
        store.add_handoff(handoff, "run_456")
        
        summary = store.get_communication_summary("run_456")
        
        assert summary["message_count"] >= 1
        assert summary["handoff_count"] >= 1
        assert "message_types" in summary
        assert "handoff" in summary["message_types"]


class TestHandoffSummary:
    """Handoff tracking tests."""

    def test_handoff_summary_with_questions(self):
        """Handoff should track open questions."""
        handoff = HandoffSummary(
            from_agent="researcher",
            to_agent="synthesizer",
            step_id="research",
            summary="Research complete",
            open_questions=["Need pricing info for option B", "Is this still current?"],
            confidence=0.7,
        )
        
        assert len(handoff.open_questions) == 2
        assert "pricing" in handoff.open_questions[0].lower()
        assert handoff.confidence == 0.7

    def test_handoff_context_summary(self):
        """Handoff should pass condensed context."""
        handoff = HandoffSummary(
            from_agent="researcher",
            to_agent="synthesizer",
            step_id="research",
            summary="Research complete",
            context_summary="Found 3 sources: A (95% relevant), B (80%), C (65%)",
            evidence_count=3,
        )
        
        assert "3 sources" in handoff.context_summary
        assert handoff.evidence_count == 3


class TestMessagePersistence:
    """Message persistence and loading tests."""

    def test_message_persists_to_disk(self):
        """Messages should persist to disk and reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = AgentMessageStore(storage_path=tmpdir)
            
            msg = AgentMessage(
                type=MessageType.HANDOFF,
                from_agent="retriever",
                to_agent="synthesizer",
                conversation_id="conv_123",
                run_id="run_456",
                subject="Test message",
                body="Test body",
            )
            
            store1.add_message(msg)
            
            # Create new store instance to test reload
            store2 = AgentMessageStore(storage_path=tmpdir)
            inbox = store2.get_inbox("run_456", "synthesizer")
            
            assert len(inbox) == 1
            assert inbox[0].subject == "Test message"

    def test_handoff_persists_to_disk(self):
        """Handoffs should persist to JSONL format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = AgentMessageStore(storage_path=tmpdir)
            
            handoff = HandoffSummary(
                from_agent="retriever",
                to_agent="synthesizer",
                step_id="step_1",
                summary="Test handoff",
                confidence=0.85,
            )
            
            store1.add_handoff(handoff, "run_456")
            
            # Create new store and reload
            store2 = AgentMessageStore(storage_path=tmpdir)
            handoffs = store2.get_handoffs("run_456")
            
            assert len(handoffs) == 1
            assert handoffs[0].summary == "Test handoff"
            assert handoffs[0].confidence == 0.85
