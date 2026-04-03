"""
Fallback plan manager for workflow recovery.

Provides hardcoded safe default plans when the planner fails or produces invalid plans.
"""

from app.schemas.plan import FallbackPlan, WorkflowPlan, WorkflowPlanTask


class FallbackPlanManager:
    """Manages fallback plans for different workflow modes."""

    def __init__(self):
        """Initialize fallback plans."""
        self._fallbacks = {
            "chat": self._build_chat_fallback(),
            "rag": self._build_rag_fallback(),
            "workflow": self._build_workflow_fallback(),
        }

    def get_fallback_plan(self, mode: str) -> WorkflowPlan:
        """
        Get fallback plan for a workflow mode.

        Args:
            mode: Workflow mode (chat, rag, workflow)

        Returns:
            WorkflowPlan: Safe fallback plan for the mode
        """
        fallback = self._fallbacks.get(mode)
        if not fallback:
            fallback = self._fallbacks["chat"]
        plan = fallback.plan
        plan.fallback_used = True
        return plan

    def _build_chat_fallback(self) -> FallbackPlan:
        """Build fallback for chat mode (simple LLM call)."""
        return FallbackPlan(
            mode="chat",
            plan=WorkflowPlan(
                version="1.0",
                tasks=[
                    WorkflowPlanTask(
                        id="direct_answer",
                        agent="writer",
                        title="Generate answer",
                        description="Use LLM to generate a direct answer to the user query",
                        depends_on=[],
                        timeout_seconds=120,
                    )
                ],
                confidence_score=0.5,
                mode="chat",
                estimated_duration_seconds=120,
            ),
            reason="Simple fallback for chat mode when planner fails",
        )

    def _build_rag_fallback(self) -> FallbackPlan:
        """Build fallback for RAG mode (retrieve, then synthesize)."""
        return FallbackPlan(
            mode="rag",
            plan=WorkflowPlan(
                version="1.0",
                tasks=[
                    WorkflowPlanTask(
                        id="retrieve_context",
                        agent="retriever",
                        title="Retrieve internal context",
                        description="Search ingested documents for relevant context",
                        depends_on=[],
                        timeout_seconds=60,
                    ),
                    WorkflowPlanTask(
                        id="synthesize",
                        agent="synthesizer",
                        title="Synthesize answer",
                        description="Combine retrieved context into a coherent answer",
                        depends_on=["retrieve_context"],
                        timeout_seconds=120,
                    ),
                    WorkflowPlanTask(
                        id="finalize",
                        agent="writer",
                        title="Write final answer",
                        description="Produce user-facing final answer",
                        depends_on=["synthesize"],
                        timeout_seconds=60,
                    ),
                ],
                confidence_score=0.6,
                mode="rag",
                estimated_duration_seconds=240,
            ),
            reason="Standard RAG pipeline when planner fails",
        )

    def _build_workflow_fallback(self) -> FallbackPlan:
        """Build fallback for workflow mode (full multi-agent pipeline)."""
        return FallbackPlan(
            mode="workflow",
            plan=WorkflowPlan(
                version="1.0",
                tasks=[
                    WorkflowPlanTask(
                        id="retrieve_context",
                        agent="retriever",
                        title="Retrieve internal context",
                        description="Search ingested documents for relevant context",
                        depends_on=[],
                        timeout_seconds=60,
                    ),
                    WorkflowPlanTask(
                        id="research_current_context",
                        agent="researcher",
                        title="Gather fresh context",
                        description="Search public web for fresh or missing context",
                        depends_on=["retrieve_context"],
                        timeout_seconds=120,
                    ),
                    WorkflowPlanTask(
                        id="draft_answer",
                        agent="synthesizer",
                        title="Draft answer",
                        description="Combine gathered context into strong answer draft",
                        depends_on=["research_current_context"],
                        timeout_seconds=120,
                    ),
                    WorkflowPlanTask(
                        id="review_draft",
                        agent="reviewer",
                        title="Review draft",
                        description="Review draft for correctness and unsupported claims",
                        depends_on=["draft_answer"],
                        timeout_seconds=90,
                    ),
                    WorkflowPlanTask(
                        id="write_final",
                        agent="writer",
                        title="Write final answer",
                        description="Produce final user-facing answer",
                        depends_on=["review_draft"],
                        timeout_seconds=60,
                    ),
                ],
                confidence_score=0.7,
                mode="workflow",
                estimated_duration_seconds=450,
            ),
            reason="Standard workflow pipeline when planner fails",
        )
