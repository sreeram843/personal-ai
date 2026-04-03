"""
Plan linter for workflow validation.

Detects cycles, orphan dependencies, max fanout violations,
depth violations, and other plan quality issues.
"""

import logging
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

from app.schemas.plan import PlanLintError, PlanLintResult, WorkflowPlan, WorkflowPlanTask


logger = logging.getLogger(__name__)


class PlanLinter:
    """Validates workflow plans for correctness and quality."""

    # Configuration for plan constraints
    MAX_TASKS = 50
    MAX_DEPTH = 10
    MAX_FANOUT = 8  # Max tasks a single task can feed into
    MAX_IN_DEGREE = 5  # Max dependencies a task can have

    BLOCKED_AGENT_NAMES = {"__init__", "system", "admin", "root", "kernel"}

    def __init__(self):
        self._errors: List[PlanLintError] = []
        self._warnings: List[PlanLintError] = []
        self._metrics: Dict[str, int] = {}

    def lint(self, plan: WorkflowPlan) -> PlanLintResult:
        """
        Lint a workflow plan and return detailed validation results.

        Args:
            plan: WorkflowPlan to validate

        Returns:
            PlanLintResult with errors, warnings, and metrics
        """
        self._errors = []
        self._warnings = []
        self._metrics = {}

        # Basic structural checks
        self._check_task_count(plan.tasks)
        self._check_task_names(plan.tasks)

        # Graph-based checks
        if not self._has_errors():
            self._check_cycles(plan.tasks)
            self._check_orphan_dependencies(plan.tasks)
            self._check_depth(plan.tasks)
            self._check_fanout(plan.tasks)
            self._check_in_degree(plan.tasks)

        # Confidence and quality checks
        self._check_confidence_score(plan)

        # Build metrics
        self._metrics = self._compute_metrics(plan.tasks)

        is_valid = len(self._errors) == 0
        return PlanLintResult(
            is_valid=is_valid,
            errors=self._errors,
            warnings=self._warnings,
            metrics=self._metrics,
        )

    def _has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self._errors) > 0

    def _check_task_count(self, tasks: List[WorkflowPlanTask]) -> None:
        """Verify task count is within limits."""
        if len(tasks) == 0:
            self._errors.append(
                PlanLintError(
                    code="NO_TASKS",
                    severity="error",
                    message="Plan must have at least one task",
                )
            )
        elif len(tasks) > self.MAX_TASKS:
            self._errors.append(
                PlanLintError(
                    code="TOO_MANY_TASKS",
                    severity="error",
                    message=f"Plan has {len(tasks)} tasks, max is {self.MAX_TASKS}",
                    details={"task_count": str(len(tasks)), "max_tasks": str(self.MAX_TASKS)},
                )
            )

    def _check_task_names(self, tasks: List[WorkflowPlanTask]) -> None:
        """Verify task and agent names are valid."""
        for task in tasks:
            # Check for reserved agent names
            if task.agent.lower() in self.BLOCKED_AGENT_NAMES:
                self._errors.append(
                    PlanLintError(
                        code="RESERVED_AGENT_NAME",
                        severity="error",
                        message=f"Agent name '{task.agent}' is reserved",
                        task_ids=[task.id],
                    )
                )

            # Check for invalid characters (basic validation)
            if not task.id.replace("_", "").replace("-", "").isalnum():
                self._warnings.append(
                    PlanLintError(
                        code="INVALID_TASK_ID_FORMAT",
                        severity="warning",
                        message=f"Task ID '{task.id}' contains unusual characters",
                        task_ids=[task.id],
                    )
                )

    def _check_cycles(self, tasks: List[WorkflowPlanTask]) -> None:
        """Detect cycles in the dependency graph using DFS."""
        task_map = {task.id: task for task in tasks}
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(task_id: str, path: List[str]) -> None:
            visited.add(task_id)
            rec_stack.add(task_id)
            path.append(task_id)

            task = task_map.get(task_id)
            if task:
                for dep in task.depends_on:
                    if dep not in visited:
                        dfs(dep, path.copy())
                    elif dep in rec_stack:
                        # Cycle detected
                        cycle_start = path.index(dep)
                        cycle = path[cycle_start:] + [dep]
                        cycles.append(cycle)

            rec_stack.discard(task_id)

        for task in tasks:
            if task.id not in visited:
                dfs(task.id, [])

        if cycles:
            cycle_str = " -> ".join(cycles[0])
            self._errors.append(
                PlanLintError(
                    code="CYCLE_DETECTED",
                    severity="error",
                    message=f"Circular dependency detected: {cycle_str}",
                    task_ids=list(set(cycle for cycle in cycles[0])),
                    details={"cycle": cycle_str, "cycle_count": str(len(cycles))},
                )
            )

    def _check_orphan_dependencies(self, tasks: List[WorkflowPlanTask]) -> None:
        """Detect unreachable tasks (orphans) in reverse dependency graph."""
        # Skip if cycles detected (already reported)
        if any(e.code == "CYCLE_DETECTED" for e in self._errors):
            return

        task_map = {task.id: task for task in tasks}
        task_ids = set(task.id for task in tasks)

        # Verify we can reach all tasks from entry points
        entry_tasks = [task_id for task_id in task_ids if not task_map[task_id].depends_on]
        if not entry_tasks:
            self._errors.append(
                PlanLintError(
                    code="NO_ENTRY_TASKS",
                    severity="error",
                    message="Plan has no entry tasks (tasks with no dependencies)",
                )
            )
            return

        # BFS to find reachable tasks from entry points
        reachable = set()
        queue = deque(entry_tasks)
        while queue:
            task_id = queue.popleft()
            if task_id in reachable:
                continue
            reachable.add(task_id)
            task = task_map.get(task_id)
            if task:
                for dep in task.depends_on:
                    if dep not in reachable:
                        queue.append(dep)

        orphans = task_ids - reachable
        if orphans:
            self._warnings.append(
                PlanLintError(
                    code="ORPHAN_TASKS",
                    severity="warning",
                    message=f"Unreachable tasks (orphans): {', '.join(sorted(orphans))}",
                    task_ids=list(orphans),
                )
            )

    def _check_depth(self, tasks: List[WorkflowPlanTask]) -> None:
        """Compute maximum dependency depth."""
        # Skip if cycles detected (already reported)
        if any(e.code == "CYCLE_DETECTED" for e in self._errors):
            self._metrics["max_depth"] = 0
            return

        task_map = {task.id: task for task in tasks}
        depths: Dict[str, int] = {}
        visiting: Set[str] = set()  # Track nodes in current DFS path

        def compute_depth(task_id: str) -> int:
            if task_id in depths:
                return depths[task_id]

            if task_id in visiting:
                # Cycle detected during traversal (shouldn't happen if cycle check ran)
                return 0

            visiting.add(task_id)
            task = task_map.get(task_id)
            if not task or not task.depends_on:
                depths[task_id] = 0
                visiting.discard(task_id)
                return 0

            max_dep_depth = max((compute_depth(dep) for dep in task.depends_on), default=0)
            depths[task_id] = max_dep_depth + 1
            visiting.discard(task_id)
            return depths[task_id]

        for task in tasks:
            compute_depth(task.id)

        max_depth = max(depths.values(), default=0)
        if max_depth > self.MAX_DEPTH:
            self._errors.append(
                PlanLintError(
                    code="MAX_DEPTH_EXCEEDED",
                    severity="error",
                    message=f"Plan depth {max_depth} exceeds limit {self.MAX_DEPTH}",
                    details={"current_depth": str(max_depth), "max_depth": str(self.MAX_DEPTH)},
                )
            )
        elif max_depth > self.MAX_DEPTH * 0.7:
            self._warnings.append(
                PlanLintError(
                    code="HIGH_DEPTH_WARNING",
                    severity="warning",
                    message=f"Plan depth {max_depth} is approaching limit {self.MAX_DEPTH}",
                    details={"current_depth": str(max_depth), "max_depth": str(self.MAX_DEPTH)},
                )
            )

        self._metrics["max_depth"] = max_depth

    def _check_fanout(self, tasks: List[WorkflowPlanTask]) -> None:
        """Check fanout (max number of tasks depending on a single task)."""
        task_ids = {task.id for task in tasks}
        fanout: Dict[str, int] = defaultdict(int)

        for task in tasks:
            for dep in task.depends_on:
                if dep in task_ids:
                    fanout[dep] += 1

        max_fanout = max(fanout.values(), default=0)
        if max_fanout > self.MAX_FANOUT:
            high_fanout_tasks = [task_id for task_id, count in fanout.items() if count > self.MAX_FANOUT]
            self._errors.append(
                PlanLintError(
                    code="MAX_FANOUT_EXCEEDED",
                    severity="error",
                    message=f"Max fanout {max_fanout} exceeds limit {self.MAX_FANOUT}",
                    task_ids=high_fanout_tasks,
                    details={"max_fanout": str(max_fanout), "max_fanout_limit": str(self.MAX_FANOUT)},
                )
            )
        elif max_fanout > self.MAX_FANOUT * 0.7:
            high_fanout_tasks = [task_id for task_id, count in fanout.items() if count > self.MAX_FANOUT * 0.7]
            self._warnings.append(
                PlanLintError(
                    code="HIGH_FANOUT_WARNING",
                    severity="warning",
                    message=f"Max fanout {max_fanout} is approaching limit {self.MAX_FANOUT}",
                    task_ids=high_fanout_tasks,
                    details={"max_fanout": str(max_fanout), "max_fanout_limit": str(self.MAX_FANOUT)},
                )
            )

        self._metrics["max_fanout"] = max_fanout

    def _check_in_degree(self, tasks: List[WorkflowPlanTask]) -> None:
        """Check in-degree (max number of dependencies a task has)."""
        max_in_degree = 0
        high_in_degree_tasks = []

        for task in tasks:
            in_degree = len(task.depends_on)
            max_in_degree = max(max_in_degree, in_degree)

            if in_degree > self.MAX_IN_DEGREE:
                high_in_degree_tasks.append(task.id)

        if high_in_degree_tasks:
            self._warnings.append(
                PlanLintError(
                    code="HIGH_IN_DEGREE",
                    severity="warning",
                    message=f"Tasks with {max_in_degree} dependencies may be hard to coordinate",
                    task_ids=high_in_degree_tasks,
                    details={"max_in_degree": str(max_in_degree), "limit": str(self.MAX_IN_DEGREE)},
                )
            )

        self._metrics["max_in_degree"] = max_in_degree

    def _check_confidence_score(self, plan: WorkflowPlan) -> None:
        """Warn if confidence score is low."""
        if plan.confidence_score < 0.3:
            self._warnings.append(
                PlanLintError(
                    code="LOW_CONFIDENCE",
                    severity="warning",
                    message=f"Plan confidence {plan.confidence_score:.2f} is below recommended 0.3",
                    details={"confidence": str(plan.confidence_score)},
                )
            )

    def _compute_metrics(self, tasks: List[WorkflowPlanTask]) -> Dict[str, int]:
        """Compute plan metrics."""
        return {
            "task_count": len(tasks),
            "max_depth": self._metrics.get("max_depth", 0),
            "max_fanout": self._metrics.get("max_fanout", 0),
            "max_in_degree": self._metrics.get("max_in_degree", 0),
        }
