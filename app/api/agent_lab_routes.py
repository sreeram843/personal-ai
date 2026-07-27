"""Agent Lab: experimental learning endpoints, isolated from production chat.

See docs/agent-lab/plan.md. Phase 1 exposes the minimal tool-calling agent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_web_search
from app.services.learn_agents.coding_agent import run_coding_agent
from app.services.learn_agents.critic_agent import run_critic_agent
from app.services.learn_agents.eval_harness import run_eval_suite, summarize
from app.services.learn_agents.memory_agent import (
    LabMemoryStore,
    get_lab_memory_store,
    run_memory_agent,
)
from app.services.learn_agents.minimal_agent import run_minimal_agent
from app.services.learn_agents.research_agent import run_research_agent
from app.services.learn_agents.tool_builder_agent import run_tool_builder_agent
from app.services.learn_agents.tracing import TraceStore, get_trace_store
from app.services.web_search import WebSearchService

router = APIRouter(prefix="/agent/lab", tags=["agent-lab"])


class MinimalAgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    include_transcript: bool = True


class MinimalAgentResponse(BaseModel):
    answer: str
    steps: int
    trace_id: str
    events: List[Dict[str, Any]] = []
    messages: List[Dict[str, Any]] = []


def get_lab_trace_store() -> TraceStore:
    return get_trace_store()


@router.post("/minimal", response_model=MinimalAgentResponse)
async def minimal_agent(
    payload: MinimalAgentRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> MinimalAgentResponse:
    trace = trace_store.new_trace(agent="minimal", query=payload.query, user_id=str(user.id))
    result = await run_minimal_agent(query=payload.query, settings=settings, trace=trace)
    trace_store.save(trace)
    return MinimalAgentResponse(
        answer=result.answer,
        steps=result.steps,
        trace_id=trace.trace_id,
        events=result.events if payload.include_transcript else [],
        messages=result.messages if payload.include_transcript else [],
    )


class ResearchAgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    include_scratchpad: bool = True


class ResearchAgentResponse(BaseModel):
    answer: str
    steps: int
    trace_id: str
    scratchpad: str = ""


@router.post("/research", response_model=ResearchAgentResponse)
async def research_agent(
    payload: ResearchAgentRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    search_service: WebSearchService = Depends(get_web_search),
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> ResearchAgentResponse:
    trace = trace_store.new_trace(agent="research", query=payload.query, user_id=str(user.id))
    result = await run_research_agent(
        query=payload.query,
        settings=settings,
        search_service=search_service,
        trace=trace,
    )
    trace_store.save(trace)
    return ResearchAgentResponse(
        answer=result.answer,
        steps=result.steps,
        trace_id=trace.trace_id,
        scratchpad=result.scratchpad if payload.include_scratchpad else "",
    )


class CodingAgentRequest(BaseModel):
    spec: str = Field(..., min_length=1, max_length=4000)
    tests: str = Field(..., min_length=1, max_length=4000)
    include_attempts: bool = True


class CodingAgentResponse(BaseModel):
    passed: bool
    code: str
    steps: int
    output: str
    trace_id: str
    attempts: List[Dict[str, Any]] = []


@router.post("/coding", response_model=CodingAgentResponse)
async def coding_agent(
    payload: CodingAgentRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> CodingAgentResponse:
    trace = trace_store.new_trace(agent="coding", query=payload.spec, user_id=str(user.id))
    result = await run_coding_agent(
        spec=payload.spec, tests=payload.tests, settings=settings, trace=trace
    )
    trace_store.save(trace)
    return CodingAgentResponse(
        passed=result.passed,
        code=result.code,
        steps=result.steps,
        output=result.output,
        trace_id=trace.trace_id,
        attempts=result.attempts if payload.include_attempts else [],
    )


class CritiqueRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)


class CritiqueResponse(BaseModel):
    draft: str
    critique: str
    scores: Dict[str, int]
    final_answer: str
    steps: int
    trace_id: str


@router.post("/critique", response_model=CritiqueResponse)
async def critique_agent(
    payload: CritiqueRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> CritiqueResponse:
    trace = trace_store.new_trace(agent="critique", query=payload.query, user_id=str(user.id))
    result = await run_critic_agent(query=payload.query, settings=settings, trace=trace)
    trace_store.save(trace)
    return CritiqueResponse(
        draft=result.draft,
        critique=result.critique,
        scores=result.scores,
        final_answer=result.final_answer,
        steps=result.steps,
        trace_id=trace.trace_id,
    )


class MemoryTurn(BaseModel):
    role: str = "user"
    content: str


class MemoryExtractRequest(BaseModel):
    turns: List[MemoryTurn] = Field(..., min_length=1)


class MemoryExtractResponse(BaseModel):
    facts: List[str]
    recall_block: str
    trace_id: str


def get_lab_memory(store: LabMemoryStore = Depends(get_lab_memory_store)) -> LabMemoryStore:
    return store


@router.post("/memory/extract", response_model=MemoryExtractResponse)
async def memory_extract(
    payload: MemoryExtractRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    trace_store: TraceStore = Depends(get_lab_trace_store),
    memory_store: LabMemoryStore = Depends(get_lab_memory),
) -> MemoryExtractResponse:
    user_id = str(user.id)
    trace = trace_store.new_trace(agent="memory", query=f"{len(payload.turns)} turns", user_id=user_id)
    result = await run_memory_agent(
        user_id=user_id,
        turns=[turn.model_dump() for turn in payload.turns],
        settings=settings,
        store=memory_store,
        trace=trace,
    )
    trace_store.save(trace)
    return MemoryExtractResponse(facts=result.facts, recall_block=result.recall_block, trace_id=trace.trace_id)


@router.get("/memory/recall")
async def memory_recall(
    user: CurrentUser,
    memory_store: LabMemoryStore = Depends(get_lab_memory),
) -> Dict[str, Any]:
    user_id = str(user.id)
    return {"facts": memory_store.get_facts(user_id), "recall_block": memory_store.get_recall_block(user_id)}


class EvalRunResponse(BaseModel):
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]


@router.post("/eval/run", response_model=EvalRunResponse)
async def eval_run(
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    search_service: WebSearchService = Depends(get_web_search),
) -> EvalRunResponse:
    results = await run_eval_suite(settings=settings, search_service=search_service)
    return EvalRunResponse(
        results=[
            {
                "task_id": r.task_id,
                "agent": r.agent,
                "description": r.description,
                "passed": r.passed,
                "judge_score": r.judge_score,
                "judge_reason": r.judge_reason,
                "output_preview": r.output_preview,
            }
            for r in results
        ],
        summary=summarize(results),
    )


class ToolBuilderRequest(BaseModel):
    tool_description: str = Field(..., min_length=1, max_length=2000)
    build_tests: str = Field(..., min_length=1, max_length=2000)
    query: str = Field(..., min_length=1, max_length=2000)


class ToolBuilderResponse(BaseModel):
    tool_name: Optional[str]
    tool_code: str
    build_passed: bool
    build_output: str
    answer: str
    steps: int
    trace_id: str


@router.post("/tool-builder", response_model=ToolBuilderResponse)
async def tool_builder_agent(
    payload: ToolBuilderRequest,
    user: CurrentUser,
    settings: Settings = Depends(get_settings),
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> ToolBuilderResponse:
    trace = trace_store.new_trace(
        agent="tool-builder", query=payload.tool_description, user_id=str(user.id)
    )
    result = await run_tool_builder_agent(
        tool_description=payload.tool_description,
        build_tests=payload.build_tests,
        query=payload.query,
        settings=settings,
        trace=trace,
    )
    trace_store.save(trace)
    return ToolBuilderResponse(
        tool_name=result.tool_name,
        tool_code=result.tool_code,
        build_passed=result.build_passed,
        build_output=result.build_output,
        answer=result.answer,
        steps=result.steps,
        trace_id=trace.trace_id,
    )


@router.get("/runs")
async def list_runs(
    user: CurrentUser,
    agent: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> Dict[str, Any]:
    return {"runs": trace_store.list_recent(agent=agent, limit=limit)}


@router.get("/runs/{trace_id}")
async def get_run(
    trace_id: str,
    user: CurrentUser,
    trace_store: TraceStore = Depends(get_lab_trace_store),
) -> Dict[str, Any]:
    trace = trace_store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
    return trace
