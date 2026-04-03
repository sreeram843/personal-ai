"""
Tests for plan linting and validation.

Covers cycle detection, orphan tasks, depth/fanout constraints,
and plan confidence scoring.
"""

import pytest

from app.schemas.plan import WorkflowPlan, WorkflowPlanTask
from app.services.plan_linter import PlanLinter


class TestPlanLinterBasic:
    """Basic plan validation tests."""

    def test_linter_accepts_valid_simple_plan(self):
        """Valid single-task plan should pass."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_1",
                    agent="worker",
                    title="Do work",
                    description="Basic work task",
                )
            ],
            confidence_score=0.8,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metrics["task_count"] == 1

    def test_linter_accepts_valid_linear_plan(self):
        """Valid chain of sequential tasks should pass."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_1",
                    agent="retriever",
                    title="Retrieve",
                    description="Get data",
                ),
                WorkflowPlanTask(
                    id="task_2",
                    agent="processor",
                    title="Process",
                    description="Process data",
                    depends_on=["task_1"],
                ),
                WorkflowPlanTask(
                    id="task_3",
                    agent="writer",
                    title="Write",
                    description="Write output",
                    depends_on=["task_2"],
                ),
            ],
            confidence_score=0.9,
            mode="workflow",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metrics["task_count"] == 3
        assert result.metrics["max_depth"] == 2

    def test_linter_rejects_empty_task_list(self):
        """Empty task list should fail at Pydantic validation."""
        with pytest.raises(ValueError, match="at least 1 item"):
            WorkflowPlan(
                tasks=[],
                confidence_score=0.5,
                mode="chat",
            )


class TestPlanLinterCycles:
    """Cycle detection tests."""

    def test_linter_detects_simple_cycle(self):
        """Task depending on itself creates cycle."""
        # Create plan manually with cycle bypassing Pydantic validator
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_1",
                    agent="worker",
                    title="Task 1",
                    description="Task 1",
                    depends_on=[],
                ),
                WorkflowPlanTask(
                    id="task_2",
                    agent="worker",
                    title="Task 2",
                    description="Task 2",
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        # Manually inject cycle for testing (bypasses Pydantic validation on depends_on)
        plan.tasks[0].depends_on = ["task_2"]
        plan.tasks[1].depends_on = ["task_1"]

        linter = PlanLinter()
        result = linter.lint(plan)

        assert not result.is_valid
        assert any(e.code == "CYCLE_DETECTED" for e in result.errors)

    def test_linter_detects_long_cycle(self):
        """Longer cycle should be detected."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="a",
                    agent="worker",
                    title="A",
                    description="A",
                ),
                WorkflowPlanTask(
                    id="b",
                    agent="worker",
                    title="B",
                    description="B",
                ),
                WorkflowPlanTask(
                    id="c",
                    agent="worker",
                    title="C",
                    description="C",
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        # Inject cycle: a -> b -> c -> a (bypasses Pydantic validation)
        plan.tasks[0].depends_on = ["c"]
        plan.tasks[1].depends_on = ["a"]
        plan.tasks[2].depends_on = ["b"]

        linter = PlanLinter()
        result = linter.lint(plan)

        assert not result.is_valid
        assert any(e.code == "CYCLE_DETECTED" for e in result.errors)


class TestPlanLinterDepth:
    """Maximum depth validation tests."""

    def test_linter_accepts_shallow_plan(self):
        """Plan within depth limit should pass."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_0",
                    agent="worker",
                    title="Task 0",
                    description="Task 0",
                ),
                WorkflowPlanTask(
                    id="task_1",
                    agent="worker",
                    title="Task 1",
                    description="Task 1",
                    depends_on=["task_0"],
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert result.metrics["max_depth"] == 1

    def test_linter_rejects_deep_plan(self):
        """Plan exceeding depth limit should fail."""
        tasks = []
        MAX_DEPTH = PlanLinter.MAX_DEPTH
        for i in range(MAX_DEPTH + 3):
            depends_on = [f"task_{i-1}"] if i > 0 else []
            tasks.append(
                WorkflowPlanTask(
                    id=f"task_{i}",
                    agent="worker",
                    title=f"Task {i}",
                    description=f"Task {i}",
                    depends_on=depends_on,
                )
            )

        plan = WorkflowPlan(
            tasks=tasks,
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert not result.is_valid
        assert any(e.code == "MAX_DEPTH_EXCEEDED" for e in result.errors)
        assert result.metrics["max_depth"] > MAX_DEPTH


class TestPlanLinterFanout:
    """Maximum fanout validation tests."""

    def test_linter_accepts_low_fanout_plan(self):
        """Plan with acceptable fanout should pass."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="root",
                    agent="worker",
                    title="Root",
                    description="Root task",
                ),
                WorkflowPlanTask(
                    id="child_1",
                    agent="worker",
                    title="Child 1",
                    description="Child 1",
                    depends_on=["root"],
                ),
                WorkflowPlanTask(
                    id="child_2",
                    agent="worker",
                    title="Child 2",
                    description="Child 2",
                    depends_on=["root"],
                ),
                WorkflowPlanTask(
                    id="child_3",
                    agent="worker",
                    title="Child 3",
                    description="Child 3",
                    depends_on=["root"],
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert result.metrics["max_fanout"] == 3

    def test_linter_rejects_high_fanout_plan(self):
        """Plan exceeding fanout limit should fail."""
        tasks = []
        MAX_FANOUT = PlanLinter.MAX_FANOUT
        tasks.append(
            WorkflowPlanTask(
                id="root",
                agent="worker",
                title="Root",
                description="Root task",
            )
        )

        # Create MAX_FANOUT + 2 child tasks all depending on root
        for i in range(MAX_FANOUT + 2):
            tasks.append(
                WorkflowPlanTask(
                    id=f"child_{i}",
                    agent="worker",
                    title=f"Child {i}",
                    description=f"Child {i}",
                    depends_on=["root"],
                )
            )

        plan = WorkflowPlan(
            tasks=tasks,
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert not result.is_valid
        assert any(e.code == "MAX_FANOUT_EXCEEDED" for e in result.errors)
        assert result.metrics["max_fanout"] > MAX_FANOUT


class TestPlanLinterOrphanTasks:
    """Orphan task detection tests."""

    def test_linter_detects_unreachable_task(self):
        """Task not reachable from entry points should be flagged."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="entry",
                    agent="worker",
                    title="Entry",
                    description="Entry task",
                ),
                WorkflowPlanTask(
                    id="second",
                    agent="worker",
                    title="Second",
                    description="Second task",
                    depends_on=["entry"],
                ),
                WorkflowPlanTask(
                    id="orphan",
                    agent="worker",
                    title="Orphan",
                    description="Orphan task (no path from entry)",
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        # This is a warning, not an error
        assert result.is_valid
        assert any(w.code == "ORPHAN_TASKS" for w in result.warnings)

    def test_linter_detects_no_entry_tasks(self):
        """Plan with all tasks having dependencies should fail."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_1",
                    agent="worker",
                    title="Task 1",
                    description="Task 1",
                ),
                WorkflowPlanTask(
                    id="task_2",
                    agent="worker",
                    title="Task 2",
                    description="Task 2",
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        # Inject circular dependencies to create no-entry scenario
        plan.tasks[0].depends_on = ["task_2"]
        plan.tasks[1].depends_on = ["task_1"]

        linter = PlanLinter()
        result = linter.lint(plan)

        # Should have cycle error
        assert not result.is_valid
        assert any(e.code == "CYCLE_DETECTED" for e in result.errors)


class TestPlanLinterTaskCount:
    """Task count constraint tests."""

    def test_linter_accepts_reasonable_task_count(self):
        """Plan with normal task count should pass."""
        tasks = []
        for i in range(10):
            tasks.append(
                WorkflowPlanTask(
                    id=f"task_{i}",
                    agent="worker",
                    title=f"Task {i}",
                    description=f"Task {i}",
                )
            )

        plan = WorkflowPlan(
            tasks=tasks,
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert result.metrics["task_count"] == 10


class TestPlanLinterConfidence:
    """Plan confidence scoring tests."""

    def test_linter_warns_low_confidence(self):
        """Plan with low confidence should warn."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_1",
                    agent="worker",
                    title="Task 1",
                    description="Task 1",
                )
            ],
            confidence_score=0.2,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid  # Still valid, just low confidence
        assert any(w.code == "LOW_CONFIDENCE" for w in result.warnings)

    def test_linter_accepts_high_confidence(self):
        """Plan with high confidence should pass cleanly."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="task_1",
                    agent="worker",
                    title="Task 1",
                    description="Task 1",
                )
            ],
            confidence_score=0.95,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert len(result.warnings) == 0


class TestPlanLinterInDegree:
    """In-degree (max dependencies per task) tests."""

    def test_linter_warns_high_in_degree(self):
        """Task with many dependencies should warn."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="root_1",
                    agent="worker",
                    title="Root 1",
                    description="Root 1",
                ),
                WorkflowPlanTask(
                    id="root_2",
                    agent="worker",
                    title="Root 2",
                    description="Root 2",
                ),
                WorkflowPlanTask(
                    id="root_3",
                    agent="worker",
                    title="Root 3",
                    description="Root 3",
                ),
                WorkflowPlanTask(
                    id="root_4",
                    agent="worker",
                    title="Root 4",
                    description="Root 4",
                ),
                WorkflowPlanTask(
                    id="root_5",
                    agent="worker",
                    title="Root 5",
                    description="Root 5",
                ),
                WorkflowPlanTask(
                    id="root_6",
                    agent="worker",
                    title="Root 6",
                    description="Root 6",
                ),
                WorkflowPlanTask(
                    id="high_in_degree",
                    agent="worker",
                    title="High in-degree",
                    description="Task with many dependencies",
                    depends_on=["root_1", "root_2", "root_3", "root_4", "root_5", "root_6"],
                ),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid  # Still valid, just warning
        assert any(w.code == "HIGH_IN_DEGREE" for w in result.warnings)


class TestPlanLinterParallelWorkflow:
    """Tests for plans with parallel task branches."""

    def test_linter_accepts_parallelizable_plan(self):
        """Plan with independent parallel branches should pass."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(
                    id="setup",
                    agent="coordinator",
                    title="Setup",
                    description="Setup",
                ),
                WorkflowPlanTask(
                    id="branch_a_1",
                    agent="worker",
                    title="Branch A Task 1",
                    description="Branch A",
                    depends_on=["setup"],
                ),
                WorkflowPlanTask(
                    id="branch_b_1",
                    agent="worker",
                    title="Branch B Task 1",
                    description="Branch B",
                    depends_on=["setup"],
                ),
                WorkflowPlanTask(
                    id="branch_a_2",
                    agent="worker",
                    title="Branch A Task 2",
                    description="Branch A Task 2",
                    depends_on=["branch_a_1"],
                ),
                WorkflowPlanTask(
                    id="branch_b_2",
                    agent="worker",
                    title="Branch B Task 2",
                    description="Branch B Task 2",
                    depends_on=["branch_b_1"],
                ),
                WorkflowPlanTask(
                    id="join",
                    agent="aggregator",
                    title="Join",
                    description="Join results",
                    depends_on=["branch_a_2", "branch_b_2"],
                ),
            ],
            confidence_score=0.85,
            mode="workflow",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.is_valid
        assert result.metrics["max_depth"] == 3  # setup -> branch -> join
        assert result.metrics["max_fanout"] == 2  # setup fans out to 2 branches


class TestPlanLinterMetrics:
    """Tests for plan metric computation."""

    def test_linter_computes_correct_metrics(self):
        """Linter should compute accurate plan metrics."""
        plan = WorkflowPlan(
            tasks=[
                WorkflowPlanTask(id="a", agent="w", title="A", description="A"),
                WorkflowPlanTask(id="b", agent="w", title="B", description="B", depends_on=["a"]),
                WorkflowPlanTask(id="c", agent="w", title="C", description="C", depends_on=["a"]),
                WorkflowPlanTask(id="d", agent="w", title="D", description="D", depends_on=["b", "c"]),
            ],
            confidence_score=0.5,
            mode="chat",
        )

        linter = PlanLinter()
        result = linter.lint(plan)

        assert result.metrics["task_count"] == 4
        assert result.metrics["max_depth"] == 2
        assert result.metrics["max_fanout"] == 2  # a fans out to b and c
        assert result.metrics["max_in_degree"] == 2  # d has 2 dependencies
