"""Tests for fallback plan manager."""

import pytest

from app.services.fallback_plan_manager import FallbackPlanManager


class TestFallbackPlanManager:
    """Tests for fallback plan manager."""

    def test_fallback_manager_initializes(self):
        """Fallback manager should initialize with all mode plans."""
        manager = FallbackPlanManager()
        assert manager is not None
        assert len(manager._fallbacks) >= 3

    def test_fallback_manager_returns_chat_plan(self):
        """Should return valid fallback for chat mode."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("chat")
        
        assert plan is not None
        assert plan.mode == "chat"
        assert plan.fallback_used is True
        assert len(plan.tasks) >= 1
        assert plan.tasks[0].agent == "writer"

    def test_fallback_manager_returns_rag_plan(self):
        """Should return valid fallback for RAG mode."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("rag")
        
        assert plan is not None
        assert plan.mode == "rag"
        assert plan.fallback_used is True
        assert len(plan.tasks) == 3  # Retrieve, synthesize, finalize
        assert "retriever" in [t.agent for t in plan.tasks]
        assert "synthesizer" in [t.agent for t in plan.tasks]
        assert "writer" in [t.agent for t in plan.tasks]

    def test_fallback_manager_returns_workflow_plan(self):
        """Should return valid fallback for workflow mode."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("workflow")
        
        assert plan is not None
        assert plan.mode == "workflow"
        assert plan.fallback_used is True
        assert len(plan.tasks) == 5  # Full pipeline
        agents = [t.agent for t in plan.tasks]
        assert "retriever" in agents
        assert "researcher" in agents
        assert "synthesizer" in agents
        assert "reviewer" in agents
        assert "writer" in agents

    def test_fallback_manager_handles_unknown_mode(self):
        """Should default to chat plan for unknown mode."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("unknown_mode")
        
        assert plan is not None
        assert plan.fallback_used is True
        # Should fall back to chat
        assert len(plan.tasks) == 1
        assert plan.tasks[0].agent == "writer"

    def test_fallback_plan_chat_valid(self):
        """Chat fallback plan should be valid."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("chat")
        
        # Verify task properties
        assert plan.tasks[0].id == "direct_answer"
        assert plan.tasks[0].title
        assert plan.tasks[0].description
        assert len(plan.tasks[0].depends_on) == 0
        assert 30 <= plan.tasks[0].timeout_seconds <= 300

    def test_fallback_plan_rag_dependencies(self):
        """RAG fallback plan should have correct dependencies."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("rag")
        
        task_ids = {t.id for t in plan.tasks}
        
        # Verify dependency chain
        retrieve = next(t for t in plan.tasks if t.id == "retrieve_context")
        synthesize = next(t for t in plan.tasks if t.id == "synthesize")
        finalize = next(t for t in plan.tasks if t.id == "finalize")
        
        assert len(retrieve.depends_on) == 0
        assert "retrieve_context" in synthesize.depends_on
        assert "synthesize" in finalize.depends_on

    def test_fallback_plan_workflow_dependencies(self):
        """Workflow fallback plan should have correct dependencies."""
        manager = FallbackPlanManager()
        plan = manager.get_fallback_plan("workflow")
        
        # Verify all tasks are reachable in dependency graph
        task_ids = {t.id: t for t in plan.tasks}
        
        # First task should have no dependencies
        first = next(t for t in plan.tasks if t.id == "retrieve_context")
        assert len(first.depends_on) == 0
        
        # Last task should depend on something
        last = next(t for t in plan.tasks if t.id == "write_final")
        assert len(last.depends_on) > 0

    def test_fallback_manager_timeout_values(self):
        """All fallback plans should have reasonable timeout values."""
        manager = FallbackPlanManager()
        
        for mode in ["chat", "rag", "workflow"]:
            plan = manager.get_fallback_plan(mode)
            
            for task in plan.tasks:
                # Timeout should be between 10 and 3600 seconds
                assert 10 <= task.timeout_seconds <= 3600
                # Default should be greater than 0
                assert task.timeout_seconds > 0

    def test_fallback_manager_confidence_scores(self):
        """Fallback plans should have reasonable confidence scores."""
        manager = FallbackPlanManager()
        
        chat_plan = manager.get_fallback_plan("chat")
        rag_plan = manager.get_fallback_plan("rag")
        workflow_plan = manager.get_fallback_plan("workflow")
        
        # All should have confidence score between 0 and 1
        assert 0 <= chat_plan.confidence_score <= 1
        assert 0 <= rag_plan.confidence_score <= 1
        assert 0 <= workflow_plan.confidence_score <= 1
        
        # Workflow should be more confident than chat
        assert workflow_plan.confidence_score > chat_plan.confidence_score

    def test_fallback_plan_estimated_durations(self):
        """Fallback plans should have realistic estimated durations."""
        manager = FallbackPlanManager()
        
        chat_plan = manager.get_fallback_plan("chat")
        rag_plan = manager.get_fallback_plan("rag")
        workflow_plan = manager.get_fallback_plan("workflow")
        
        # All should be between 10 seconds and 2 hours
        assert 10 <= chat_plan.estimated_duration_seconds <= 7200
        assert 10 <= rag_plan.estimated_duration_seconds <= 7200
        assert 10 <= workflow_plan.estimated_duration_seconds <= 7200
        
        # Chat should be fastest, workflow slowest
        assert chat_plan.estimated_duration_seconds < rag_plan.estimated_duration_seconds
        assert rag_plan.estimated_duration_seconds < workflow_plan.estimated_duration_seconds
