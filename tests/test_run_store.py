"""Tests for run store and checkpoint management."""

import tempfile
from datetime import datetime
from pathlib import Path

from app.schemas.run import ErrorCategory, RunStatus, StepState, WorkflowCheckpoint, WorkflowRun
from app.services.run_store import RunStore


def test_run_store_creates_run() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow", conversation_id="conv-1")

        assert run.run_id is not None
        assert run.mode == "workflow"
        assert run.conversation_id == "conv-1"
        assert run.status == RunStatus.PENDING
        assert run.created_at is not None


def test_run_store_retrieves_run() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        created_run = store.create_run(mode="chat", conversation_id="conv-1")

        retrieved_run = store.get_run(created_run.run_id)
        assert retrieved_run is not None
        assert retrieved_run.run_id == created_run.run_id
        assert retrieved_run.mode == "chat"


def test_run_store_updates_run_status() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow")

        # Start run
        updated = store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
        assert updated.status == RunStatus.IN_PROGRESS
        assert updated.started_at is not None

        # Complete run
        updated = store.update_run_status(run.run_id, RunStatus.COMPLETED)
        assert updated.status == RunStatus.COMPLETED
        assert updated.completed_at is not None


def test_run_store_persists_across_instances() -> None:
    """Test that runs persist to disk and are retrievable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create run in first store instance
        store1 = RunStore(storage_path=tmpdir)
        run = store1.create_run(mode="workflow", conversation_id="conv-1")
        run_id = run.run_id

        # Retrieve in second store instance (new cache)
        store2 = RunStore(storage_path=tmpdir)
        retrieved = store2.get_run(run_id)

        assert retrieved is not None
        assert retrieved.run_id == run_id
        assert retrieved.conversation_id == "conv-1"


def test_run_store_adds_checkpoints() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow")

        checkpoint = WorkflowCheckpoint(
            step_id="step_1",
            run_id=run.run_id,
            agent="researcher",
            state=StepState.COMPLETED,
            inputs={"query": "test"},
            outputs="test result",
        )

        updated_run = store.add_checkpoint(run.run_id, checkpoint)
        assert len(updated_run.checkpoints) == 1
        assert updated_run.checkpoints[0].step_id == "step_1"


def test_run_store_updates_checkpoint() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow")

        checkpoint = WorkflowCheckpoint(
            step_id="step_1",
            run_id=run.run_id,
            agent="researcher",
            state=StepState.RUNNING,
            inputs={"query": "test"},
        )
        store.add_checkpoint(run.run_id, checkpoint)

        # Update checkpoint
        updated = store.update_checkpoint(
            run.run_id,
            "step_1",
            state=StepState.COMPLETED,
            output="result data",
        )

        assert updated.state == StepState.COMPLETED
        assert updated.outputs == "result data"
        assert updated.completed_at is not None


def test_run_store_creates_retry_run() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        original_run = store.create_run(mode="workflow")

        # Add checkpoint to original
        checkpoint = WorkflowCheckpoint(
            step_id="step_1",
            run_id=original_run.run_id,
            agent="researcher",
            inputs={"query": "test"},
        )
        store.add_checkpoint(original_run.run_id, checkpoint)

        # Mark original as failed
        store.update_run_status(original_run.run_id, RunStatus.FAILED, "timeout")
        original_run.error_category = ErrorCategory.TRANSIENT

        # Create retry run
        retry_run = store.create_retry_run(original_run.run_id)

        assert retry_run is not None
        assert retry_run.parent_run_id == original_run.run_id
        assert retry_run.retry_count == 1
        assert len(retry_run.checkpoints) == 1


def test_run_store_lists_runs_by_conversation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)

        # Create multiple runs for different conversations
        run1 = store.create_run(mode="chat", conversation_id="conv-1")
        run2 = store.create_run(mode="workflow", conversation_id="conv-1")
        run3 = store.create_run(mode="rag", conversation_id="conv-2")

        # List conv-1 runs
        conv1_runs = store.list_runs_by_conversation("conv-1")
        assert len(conv1_runs) == 2
        assert all(r.conversation_id == "conv-1" for r in conv1_runs)

        # List conv-2 runs
        conv2_runs = store.list_runs_by_conversation("conv-2")
        assert len(conv2_runs) == 1
        assert conv2_runs[0].conversation_id == "conv-2"


def test_run_store_retry_policy_checks() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow")

        # Mark as failed with transient error
        store.update_run_status(run.run_id, RunStatus.FAILED, "timeout")
        run = store.get_run(run.run_id)
        run.error_category = ErrorCategory.TRANSIENT

        should_retry, retrieved_run = store.should_retry_run(run.run_id)
        assert should_retry is True

        # Simulate retries until exhausted
        for i in range(3):
            run = store.get_run(run.run_id)
            run.retry_count = i
            store._persist_run(run)

        # After max retries, should not retry
        run = store.get_run(run.run_id)
        run.retry_count = 3
        store._persist_run(run)

        should_retry, _ = store.should_retry_run(run.run_id)
        assert should_retry is False


def test_run_store_permanent_errors_not_retried() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow")

        # Mark as failed with permanent error
        store.update_run_status(run.run_id, RunStatus.FAILED, "invalid input")
        run = store.get_run(run.run_id)
        run.error_category = ErrorCategory.PERMANENT

        should_retry, _ = store.should_retry_run(run.run_id)
        # Permanent errors should not be retried
        assert should_retry is False


def test_workflow_checkpoint_dependencies() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow")

        # Create checkpoints with dependencies
        cp1 = WorkflowCheckpoint(
            step_id="step_1",
            run_id=run.run_id,
            agent="coordinator",
            depends_on=[],
        )
        cp2 = WorkflowCheckpoint(
            step_id="step_2",
            run_id=run.run_id,
            agent="researcher",
            depends_on=["step_1"],
        )
        cp3 = WorkflowCheckpoint(
            step_id="step_3",
            run_id=run.run_id,
            agent="synthesizer",
            depends_on=["step_1", "step_2"],
        )

        store.add_checkpoint(run.run_id, cp1)
        store.add_checkpoint(run.run_id, cp2)
        store.add_checkpoint(run.run_id, cp3)

        checkpoints = store.get_run_checkpoints(run.run_id)
        assert len(checkpoints) == 3
        assert checkpoints[1].depends_on == ["step_1"]
        assert checkpoints[2].depends_on == ["step_1", "step_2"]


def test_run_store_appends_event_ledger() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(storage_path=tmpdir)
        run = store.create_run(mode="workflow", conversation_id="conv-evt")

        store.update_run_status(run.run_id, RunStatus.IN_PROGRESS)
        store.update_run_status(run.run_id, RunStatus.FAILED, "connection timeout")

        events = store.get_run_events(run.run_id)
        event_types = [event.event_type.value for event in events]

        assert "run_created" in event_types
        assert event_types.count("status_changed") >= 2

        loaded = store.get_run(run.run_id)
        assert loaded is not None
        assert loaded.error_fingerprint == "timeout"
        assert loaded.error_category == ErrorCategory.TRANSIENT
