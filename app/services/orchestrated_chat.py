from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Sequence

from app.services.llm_gateway import LLMGateway, WorkflowModelProfile
from app.schemas.chat import ChatResponse, RetrievedChunk, WorkflowStep, WorkflowTrace
from app.services.ollama import OllamaClient
from app.services.vector_store import VectorStore
from app.services.web_search import WebSearchService, should_prioritize_fresh_web_data
from app.services.workflow_memory import WorkflowMemoryStore
from app.services.workflow_roles import DEFAULT_WORKFLOW_ROLES


ModeName = Literal["chat", "rag", "workflow"]
SUPPORTED_AGENTS = set(DEFAULT_WORKFLOW_ROLES)
TASK_TOKEN_COST = {
    "retriever": 250,
    "researcher": 350,
    "synthesizer": 900,
    "reviewer": 450,
    "writer": 700,
}


@dataclass
class PlannedTask:
    id: str
    agent: str
    title: str
    description: str
    depends_on: List[str] = field(default_factory=list)


@dataclass
class TaskOutcome:
    status: Literal["completed", "failed", "skipped"]
    summary: str
    output: str = ""
    sources: List[RetrievedChunk] = field(default_factory=list)


class OrchestratedChatService:
    def __init__(
        self,
        *,
        embed_client: OllamaClient,
        llm_gateway: LLMGateway,
        model_profile: WorkflowModelProfile,
        web_search: WebSearchService,
        vector_store: VectorStore,
        memory_store: WorkflowMemoryStore,
    ) -> None:
        self._embed_client = embed_client
        self._llm_gateway = llm_gateway
        self._model_profile = model_profile
        self._web_search = web_search
        self._vector_store = vector_store
        self._memory_store = memory_store

    async def run_mode(
        self,
        *,
        mode: ModeName,
        query: str,
        system_prompt: str,
        chat_history: Sequence[Dict[str, str]],
        conversation_id: Optional[str],
        top_k: int,
        score_threshold: Optional[float],
        options: Dict[str, Any],
        use_rag: bool,
        include_trace: bool,
        persist_memory: bool,
        max_steps: int,
    ) -> ChatResponse:
        final_response: Optional[ChatResponse] = None
        async for event in self.stream_mode(
            mode=mode,
            query=query,
            system_prompt=system_prompt,
            chat_history=chat_history,
            conversation_id=conversation_id,
            top_k=top_k,
            score_threshold=score_threshold,
            options=options,
            use_rag=use_rag,
            include_trace=include_trace,
            persist_memory=persist_memory,
            max_steps=max_steps,
        ):
            if event["type"] == "final":
                final_response = ChatResponse(**event["response"])
        if final_response is None:
            raise RuntimeError("Workflow execution completed without a final response")
        return final_response

    async def stream_mode(
        self,
        *,
        mode: ModeName,
        query: str,
        system_prompt: str,
        chat_history: Sequence[Dict[str, str]],
        conversation_id: Optional[str],
        top_k: int,
        score_threshold: Optional[float],
        options: Dict[str, Any],
        use_rag: bool,
        include_trace: bool,
        persist_memory: bool,
        max_steps: int,
    ) -> AsyncIterator[Dict[str, Any]]:
        memory_summary = ""
        if persist_memory and conversation_id:
            memory_summary = await self._memory_store.get_summary(conversation_id)
            summary_text = memory_summary or "No prior workflow memory found for this conversation."
            yield {
                "type": "memory",
                "phase": "read",
                "summary": summary_text,
                "conversation_id": conversation_id,
            }

        state: Dict[str, Any] = {
            "query": query,
            "system_prompt": system_prompt,
            "chat_history": list(chat_history),
            "conversation_id": conversation_id,
            "memory_summary": memory_summary,
            "retrieval_context": "",
            "web_context": "",
            "draft": "",
            "review_notes": "",
            "final_answer": "",
            "evidence_ids": [],
            "reviewer_quorum": int(options.get("reviewer_quorum", 2)),
            "require_evidence_markers": bool(options.get("require_evidence_markers", True)),
            "trust_lanes_enabled": bool(options.get("trust_lanes_enabled", True)),
            "token_budget": options.get("token_budget"),
        }
        aggregated_sources: List[RetrievedChunk] = []
        trace = WorkflowTrace(status="partial", steps=[])

        tasks, plan_summary = await self._build_plan(
            mode=mode,
            query=query,
            system_prompt=system_prompt,
            chat_history=chat_history,
            memory_summary=memory_summary,
            options=options,
            use_rag=use_rag,
            max_steps=max_steps,
        )
        tasks = self._apply_budget_policy(tasks, state.get("token_budget"))

        if include_trace:
            trace.steps.append(
                WorkflowStep(
                    id="plan",
                    agent="coordinator",
                    title="Build workflow plan",
                    status="completed",
                    summary=plan_summary,
                )
            )
            yield {"type": "workflow", "workflow": trace.model_dump()}

            for task in tasks:
                trace.steps.append(
                    WorkflowStep(
                        id=task.id,
                        agent=task.agent,
                        title=task.title,
                        status="planned",
                        depends_on=task.depends_on,
                    )
                )
            yield {"type": "workflow", "workflow": trace.model_dump()}

        pending = {task.id: task for task in tasks}
        completed: set[str] = set()

        while pending:
            ready = [task for task in pending.values() if all(dep in completed for dep in task.depends_on)]
            if not ready:
                trace.status = "partial"
                if include_trace:
                    for task in pending.values():
                        self._update_trace_step(trace, task.id, "failed", "Blocked by unresolved dependencies.")
                    yield {"type": "workflow", "workflow": trace.model_dump()}
                break

            for task in ready:
                if include_trace:
                    self._update_trace_step(trace, task.id, "in_progress", f"{task.agent} is running.")
                    yield {"type": "workflow", "workflow": trace.model_dump()}

                outcome = await self._execute_task(
                    task=task,
                    state=state,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    options=options,
                    use_rag=use_rag,
                )
                pending.pop(task.id, None)
                completed.add(task.id)
                aggregated_sources.extend(outcome.sources)
                if outcome.sources:
                    yield {
                        "type": "sources",
                        "step_id": task.id,
                        "agent": task.agent,
                        "sources": [source.model_dump() for source in outcome.sources],
                    }
                if include_trace:
                    self._update_trace_step(trace, task.id, outcome.status, outcome.summary)
                    yield {"type": "workflow", "workflow": trace.model_dump()}

        final_message = state.get("final_answer") or state.get("draft")
        if not final_message:
            final_message = await self._chat_text(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "system", "content": DEFAULT_WORKFLOW_ROLES["writer"].instruction},
                    {"role": "user", "content": self._build_final_prompt(state)},
                ],
                options,
                stage="writer",
            )

        trace.status = self._derive_trace_status(trace)

        if persist_memory and conversation_id:
            memory_entries = [
                {
                    "agent": step.agent,
                    "title": step.title,
                    "summary": step.summary or step.status,
                }
                for step in trace.steps
                if step.agent != "coordinator" or step.id == "plan"
            ] + [{"agent": "writer", "title": "Final answer", "summary": final_message[:600]}]

            await self._memory_store.append_entries(
                conversation_id,
                memory_entries,
            )
            yield {
                "type": "memory",
                "phase": "write",
                "summary": f"Stored {len(memory_entries)} workflow memory entries.",
                "conversation_id": conversation_id,
            }

        response = ChatResponse(
            message=final_message,
            sources=self._dedupe_sources(aggregated_sources),
            workflow=trace if include_trace else None,
        )
        yield {"type": "final", "response": response.model_dump()}

    async def _build_plan(
        self,
        *,
        mode: ModeName,
        query: str,
        system_prompt: str,
        chat_history: Sequence[Dict[str, str]],
        memory_summary: str,
        options: Dict[str, Any],
        use_rag: bool,
        max_steps: int,
    ) -> tuple[List[PlannedTask], str]:
        if mode != "workflow":
            return self._static_plan(mode, use_rag), f"Static {mode} workflow selected."

        history_block = self._format_history(chat_history)
        planner_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": DEFAULT_WORKFLOW_ROLES["coordinator"].instruction},
            {
                "role": "system",
                "content": (
                    "Return JSON only as an array. Each task must include id, agent, title, description, depends_on. "
                    f"Allowed agents: {', '.join(sorted(SUPPORTED_AGENTS))}. Limit the plan to {max_steps} tasks."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User goal:\n{query}\n\n"
                    f"Recent chat history:\n{history_block or 'No prior chat history.'}\n\n"
                    f"Prior workflow memory:\n{memory_summary or 'No prior workflow memory.'}\n\n"
                    f"use_rag={'true' if use_rag else 'false'}"
                ),
            },
        ]
        raw_plan = await self._chat_text(planner_messages, options, stage="planner")
        parsed = self._parse_plan(raw_plan)
        if parsed:
            verified = await self._verify_plan(
                query=query,
                system_prompt=system_prompt,
                raw_plan=raw_plan,
                options=options,
                max_steps=max_steps,
            )
            if verified:
                return verified[:max_steps], "Planner verifier accepted and refined the task graph."
            return parsed[:max_steps], "Planner generated a task graph; verifier fallback kept draft plan."
        return self._static_plan(mode, use_rag), "Planner returned invalid JSON, so the fallback workflow was used."

    async def _verify_plan(
        self,
        *,
        query: str,
        system_prompt: str,
        raw_plan: str,
        options: Dict[str, Any],
        max_steps: int,
    ) -> List[PlannedTask]:
        verifier_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": DEFAULT_WORKFLOW_ROLES["coordinator"].instruction},
            {
                "role": "system",
                "content": (
                    "You are the plan verifier. Validate dependencies and remove unnecessary tasks. "
                    "Return JSON array only with id, agent, title, description, depends_on."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Goal:\n{query}\n\n"
                    f"Draft plan JSON:\n{raw_plan}\n\n"
                    f"Keep at most {max_steps} tasks and keep a writer stage."
                ),
            },
        ]
        verified_raw = await self._chat_text(verifier_messages, options, stage="planner")
        return self._parse_plan(verified_raw)

    def _static_plan(self, mode: ModeName, use_rag: bool) -> List[PlannedTask]:
        tasks: List[PlannedTask] = []
        if mode in {"rag", "workflow"} and use_rag:
            tasks.append(
                PlannedTask(
                    id="retrieve_context",
                    agent="retriever",
                    title="Retrieve internal context",
                    description="Search ingested documents for relevant internal context.",
                )
            )
        research_depends_on = ["retrieve_context"] if tasks else []
        synth_depends_on = list(research_depends_on)
        tasks.append(
            PlannedTask(
                id="research_current_context",
                agent="researcher",
                title="Gather fresh external context",
                description="Search the public web for fresh or missing context when needed.",
                depends_on=research_depends_on,
            )
        )
        synth_depends_on.append("research_current_context")
        tasks.extend(
            [
                PlannedTask(
                    id="draft_answer",
                    agent="synthesizer",
                    title="Draft answer",
                    description="Combine the gathered context into a strong answer draft.",
                    depends_on=synth_depends_on,
                ),
                PlannedTask(
                    id="review_draft",
                    agent="reviewer",
                    title="Review draft",
                    description="Review the draft for correctness and unsupported claims.",
                    depends_on=["draft_answer"],
                ),
                PlannedTask(
                    id="write_final",
                    agent="writer",
                    title="Write final answer",
                    description="Produce the final user-facing answer.",
                    depends_on=["review_draft"],
                ),
            ]
        )
        return tasks

    async def _execute_task(
        self,
        *,
        task: PlannedTask,
        state: Dict[str, Any],
        top_k: int,
        score_threshold: Optional[float],
        options: Dict[str, Any],
        use_rag: bool,
    ) -> TaskOutcome:
        if task.agent == "retriever":
            return await self._run_retriever(state, top_k, score_threshold, use_rag)
        if task.agent == "researcher":
            return await self._run_researcher(state)
        if task.agent == "synthesizer":
            return await self._run_synthesizer(state, options)
        if task.agent == "reviewer":
            return await self._run_reviewer(state, options)
        if task.agent == "writer":
            return await self._run_writer(state, options)
        return TaskOutcome(status="skipped", summary=f"Unsupported agent '{task.agent}' was skipped.")

    async def _run_retriever(
        self,
        state: Dict[str, Any],
        top_k: int,
        score_threshold: Optional[float],
        use_rag: bool,
    ) -> TaskOutcome:
        if not use_rag:
            state["retrieval_context"] = ""
            return TaskOutcome(status="skipped", summary="Local retrieval disabled for this run.")

        embeddings = await self._embed_client.embed([state["query"]])
        results = self._vector_store.search(
            embeddings[0],
            limit=top_k,
            score_threshold=score_threshold,
        )
        if not results:
            state["retrieval_context"] = ""
            return TaskOutcome(status="completed", summary="No matching internal documents were found.")

        sections: List[str] = []
        sources: List[RetrievedChunk] = []
        for index, result in enumerate(results, start=1):
            payload = result.payload or {}
            text = str(payload.get("text", ""))
            metadata = {key: value for key, value in payload.items() if key != "text"}
            metadata["trust_lane"] = "retrieved" if state.get("trust_lanes_enabled", True) else ""
            label = str(metadata.get("path") or metadata.get("name") or metadata.get("title") or result.id)
            sections.append(f"[Document {index}] {label}\n{text}")
            sources.append(
                RetrievedChunk(
                    id=str(result.id),
                    score=float(result.score),
                    text=text,
                    metadata=metadata,
                )
            )
        state["evidence_ids"] = [source.id for source in sources]
        state["retrieval_context"] = "\n\n".join(sections)
        return TaskOutcome(
            status="completed",
            summary=f"Collected {len(sources)} internal document matches.",
            output=state["retrieval_context"],
            sources=sources,
        )

    async def _run_researcher(self, state: Dict[str, Any]) -> TaskOutcome:
        should_search = should_prioritize_fresh_web_data(state["query"]) or not state.get("retrieval_context")
        if not should_search:
            state["web_context"] = ""
            return TaskOutcome(status="skipped", summary="Fresh web research was not needed for this query.")

        results = await self._web_search.search_with_page_excerpts(state["query"])
        if not results:
            state["web_context"] = ""
            return TaskOutcome(status="completed", summary="No fresh web results were available.")

        state["web_context"] = WebSearchService.format_results_for_context(results)
        sources = [
            RetrievedChunk(
                id=str(item.get("href") or f"web-{index}"),
                score=0.0,
                text=str(item.get("excerpt") or item.get("body") or ""),
                metadata={
                    "title": item.get("title", ""),
                    "name": item.get("title", ""),
                    "path": item.get("href", ""),
                    "fetched_at_utc": item.get("fetched_at_utc", ""),
                    "source": "web",
                    "trust_lane": "verified_web" if state.get("trust_lanes_enabled", True) else "",
                },
            )
            for index, item in enumerate(results, start=1)
        ]
        return TaskOutcome(
            status="completed",
            summary=f"Collected {len(sources)} fresh web results.",
            output=state["web_context"],
            sources=sources,
        )

    async def _run_synthesizer(self, state: Dict[str, Any], options: Dict[str, Any]) -> TaskOutcome:
        evidence_catalog = self._build_evidence_catalog(state)
        draft = await self._chat_text(
            [
                {"role": "system", "content": state["system_prompt"]},
                {"role": "system", "content": DEFAULT_WORKFLOW_ROLES["synthesizer"].instruction},
                {
                    "role": "user",
                    "content": (
                        f"{self._build_synthesis_prompt(state)}\n\n"
                        "For each factual claim, append one or more markers in the form [[evidence:<id>]].\n"
                        f"Available evidence IDs:\n{evidence_catalog}"
                    ),
                },
            ],
            options,
            stage="synthesizer",
        )
        if state.get("require_evidence_markers", True) and state.get("evidence_ids"):
            if not self._validate_evidence_markers(draft, state["evidence_ids"]):
                draft = (
                    "I cannot verify key claims from the available evidence. "
                    "Please review the cited sources or broaden retrieval before finalizing."
                )
        state["draft"] = draft
        return TaskOutcome(status="completed", summary="Produced a draft answer.", output=draft)

    async def _run_reviewer(self, state: Dict[str, Any], options: Dict[str, Any]) -> TaskOutcome:
        quorum = max(1, min(int(state.get("reviewer_quorum", 2)), 3))
        reviews: List[str] = []
        for idx in range(quorum):
            review = await self._chat_text(
                [
                    {"role": "system", "content": state["system_prompt"]},
                    {"role": "system", "content": DEFAULT_WORKFLOW_ROLES["reviewer"].instruction},
                    {
                        "role": "user",
                        "content": (
                            f"Reviewer {idx + 1}/{quorum}. Prioritize independently discovered issues.\n\n"
                            f"User request:\n{state['query']}\n\n"
                            f"Draft answer:\n{state.get('draft') or 'No draft available.'}"
                        ),
                    },
                ],
                options,
                stage="reviewer",
            )
            reviews.append(review)
        review_text = "\n\n".join(f"Reviewer {idx + 1}: {text}" for idx, text in enumerate(reviews))
        state["review_notes"] = review_text
        return TaskOutcome(
            status="completed",
            summary=f"Reviewed the draft with quorum={quorum} and produced revision notes.",
            output=review_text,
        )

    async def _run_writer(self, state: Dict[str, Any], options: Dict[str, Any]) -> TaskOutcome:
        final_answer = await self._chat_text(
            [
                {"role": "system", "content": state["system_prompt"]},
                {"role": "system", "content": DEFAULT_WORKFLOW_ROLES["writer"].instruction},
                {"role": "user", "content": self._build_final_prompt(state)},
            ],
            options,
            stage="writer",
        )
        state["final_answer"] = final_answer
        return TaskOutcome(status="completed", summary="Produced the final answer.", output=final_answer)

    async def _chat_text(
        self,
        messages: Sequence[Dict[str, str]],
        options: Dict[str, Any],
        *,
        stage: Literal["planner", "synthesizer", "reviewer", "writer"],
    ) -> str:
        stage_config = getattr(self._model_profile, stage)
        return await self._llm_gateway.generate(
            messages=messages,
            model=stage_config.model,
            provider=stage_config.provider,
            options=options,
        )

    def _parse_plan(self, raw: str) -> List[PlannedTask]:
        candidate = raw.strip()
        fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", candidate, flags=re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1)
        else:
            array_match = re.search(r"(\[[\s\S]*\])", candidate)
            if array_match:
                candidate = array_match.group(1)
        try:
            items = json.loads(candidate)
        except json.JSONDecodeError:
            return []
        if not isinstance(items, list):
            return []

        tasks: List[PlannedTask] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("id") or f"task_{index}").strip().lower().replace(" ", "_")
            agent = self._normalize_agent(str(item.get("agent") or ""))
            if not task_id or task_id in seen_ids or agent not in SUPPORTED_AGENTS:
                continue
            seen_ids.add(task_id)
            depends_on = item.get("depends_on") or item.get("dependsOn") or []
            tasks.append(
                PlannedTask(
                    id=task_id,
                    agent=agent,
                    title=str(item.get("title") or f"Task {index}").strip(),
                    description=str(item.get("description") or item.get("title") or f"Task {index}").strip(),
                    depends_on=[str(dep).strip() for dep in depends_on if str(dep).strip()],
                )
            )
        valid_ids = {task.id for task in tasks}
        for task in tasks:
            task.depends_on = [dep for dep in task.depends_on if dep in valid_ids and dep != task.id]
        return tasks

    def _normalize_agent(self, raw: str) -> str:
        value = raw.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "planner": "coordinator",
            "plan": "coordinator",
            "research": "researcher",
            "analyst": "synthesizer",
            "critic": "reviewer",
            "editor": "writer",
        }
        return aliases.get(value, value)

    def _format_history(self, chat_history: Sequence[Dict[str, str]]) -> str:
        lines: List[str] = []
        for item in chat_history[-8:]:
            role = str(item.get("role") or "user").upper()
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_synthesis_prompt(self, state: Dict[str, Any]) -> str:
        return (
            f"User request:\n{state['query']}\n\n"
            f"Recent chat history:\n{self._format_history(state['chat_history']) or 'No prior chat history.'}\n\n"
            f"Prior workflow memory:\n{state.get('memory_summary') or 'No prior workflow memory.'}\n\n"
            f"Internal document context:\n{state.get('retrieval_context') or 'No internal context available.'}\n\n"
            f"Fresh web context:\n{state.get('web_context') or 'No fresh web context available.'}"
        )

    def _build_final_prompt(self, state: Dict[str, Any]) -> str:
        return (
            f"User request:\n{state['query']}\n\n"
            f"Prior workflow memory:\n{state.get('memory_summary') or 'No prior workflow memory.'}\n\n"
            f"Draft answer:\n{state.get('draft') or 'No draft available.'}\n\n"
            f"Reviewer notes:\n{state.get('review_notes') or 'No review notes available.'}\n\n"
            f"Internal document context:\n{state.get('retrieval_context') or 'No internal context available.'}\n\n"
            f"Fresh web context:\n{state.get('web_context') or 'No fresh web context available.'}"
        )

    def _update_trace_step(
        self,
        trace: WorkflowTrace,
        step_id: str,
        status: Literal["planned", "in_progress", "completed", "failed", "skipped"],
        summary: str,
    ) -> None:
        for index, step in enumerate(trace.steps):
            if step.id == step_id:
                trace.steps[index] = WorkflowStep(
                    id=step.id,
                    agent=step.agent,
                    title=step.title,
                    status=status,
                    summary=summary,
                    depends_on=step.depends_on,
                )
                return

    def _derive_trace_status(self, trace: WorkflowTrace) -> Literal["completed", "failed", "partial"]:
        statuses = {step.status for step in trace.steps}
        if "failed" in statuses and "completed" not in statuses:
            return "failed"
        if "failed" in statuses or "skipped" in statuses:
            return "partial"
        return "completed"

    def _dedupe_sources(self, sources: Sequence[RetrievedChunk]) -> List[RetrievedChunk]:
        deduped: List[RetrievedChunk] = []
        seen: set[str] = set()
        for source in sources:
            key = source.id or str(source.metadata.get("path") or source.metadata.get("title") or "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped

    def _build_evidence_catalog(self, state: Dict[str, Any]) -> str:
        ids = state.get("evidence_ids") or []
        if not ids:
            return "No evidence IDs available"
        return "\n".join(f"- {evidence_id}" for evidence_id in ids)

    def _validate_evidence_markers(self, draft: str, evidence_ids: Sequence[str]) -> bool:
        markers = re.findall(r"\[\[evidence:([^\]]+)\]\]", draft)
        if not markers:
            return False
        allowed = set(evidence_ids)
        return any(marker.strip() in allowed for marker in markers)

    def _apply_budget_policy(self, tasks: List[PlannedTask], token_budget: Optional[int]) -> List[PlannedTask]:
        if token_budget is None or token_budget <= 0:
            return tasks
        total = 0
        selected: List[PlannedTask] = []
        for task in tasks:
            cost = TASK_TOKEN_COST.get(task.agent, 300)
            if selected and total + cost > token_budget and task.agent != "writer":
                continue
            selected.append(task)
            total += cost
        if not any(task.agent == "writer" for task in selected):
            selected.append(
                PlannedTask(
                    id="write_final",
                    agent="writer",
                    title="Write final answer",
                    description="Produce the final user-facing answer.",
                    depends_on=[selected[-1].id] if selected else [],
                )
            )
        valid_ids = {task.id for task in selected}
        for task in selected:
            task.depends_on = [dep for dep in task.depends_on if dep in valid_ids]
        return selected


__all__ = ["OrchestratedChatService"]