"""Agent diagnostics, skills, and task management."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.deps import (
    get_agent_task_store,
    get_mcp_server_store,
    get_skill_catalog,
    get_skill_store,
    get_tool_registry,
)
from app.schemas.agent import (
    AgentTaskCreate,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTaskStatusUpdate,
    AssistantCreate,
    AssistantListResponse,
    AssistantResponse,
    AssistantUpdate,
    DoctorReportResponse,
    SkillCreate,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)
from app.services.agent_task_store import AgentTaskStore
from app.services.diagnostics import build_doctor_report
from app.services.mcp_store import McpServerStore
from app.services.skill_loader import SkillCatalog, SkillRecord, SkillStore
from app.services.tool_registry import ToolRegistry

router = APIRouter(prefix="/agent", tags=["agent"])


def _skill_to_response(skill: SkillRecord) -> SkillResponse:
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        triggers=skill.triggers,
        allowed_tools=skill.allowed_tools,
        enabled=skill.enabled,
        bundled=skill.bundled,
        pick_only=skill.pick_only,
    )


def _assistant_to_response(skill: SkillRecord) -> AssistantResponse:
    return AssistantResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        instructions=skill.system_addendum,
        triggers=skill.triggers,
        allowed_tools=skill.allowed_tools,
        enabled=skill.enabled,
        bundled=skill.bundled,
        pick_only=skill.pick_only,
        is_default=False,
    )


DEFAULT_ASSISTANT = AssistantResponse(
    id="default",
    name="CurieAI",
    description="General assistant with live data, tools, and document search.",
    instructions="",
    triggers=[],
    allowed_tools=[],
    enabled=True,
    bundled=True,
    pick_only=False,
    is_default=True,
)


@router.get("/diagnostics", response_model=DoctorReportResponse)
async def agent_diagnostics(
    user: CurrentUser,
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    mcp_store: McpServerStore = Depends(get_mcp_server_store),
    skill_catalog: SkillCatalog = Depends(get_skill_catalog),
) -> DoctorReportResponse:
    settings = get_settings()
    report = await build_doctor_report(
        settings=settings,
        user_id=str(user.id),
        tool_registry=tool_registry,
        mcp_store=mcp_store,
        skill_catalog=skill_catalog,
    )
    return DoctorReportResponse.model_validate(report)


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    user: CurrentUser,
    skill_catalog: SkillCatalog = Depends(get_skill_catalog),
) -> SkillListResponse:
    skills = [_skill_to_response(item) for item in skill_catalog.list_for_user(str(user.id))]
    return SkillListResponse(skills=skills)


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillCreate,
    user: CurrentUser,
    skill_store: SkillStore = Depends(get_skill_store),
) -> SkillResponse:
    created = skill_store.create(
        user_id=str(user.id),
        name=payload.name,
        description=payload.description,
        triggers=payload.triggers,
        allowed_tools=payload.allowed_tools,
        system_addendum=payload.system_addendum,
    )
    return _skill_to_response(created)


@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    payload: SkillUpdate,
    user: CurrentUser,
    skill_catalog: SkillCatalog = Depends(get_skill_catalog),
    skill_store: SkillStore = Depends(get_skill_store),
) -> SkillResponse:
    current = next(
        (item for item in skill_catalog.list_for_user(str(user.id)) if item.id == skill_id),
        None,
    )
    if current is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    if current.bundled:
        if payload.enabled is None:
            return _skill_to_response(current)
        skill_store.set_bundled_preference(str(user.id), skill_id, enabled=payload.enabled)
        refreshed = next(item for item in skill_catalog.list_for_user(str(user.id)) if item.id == skill_id)
        return _skill_to_response(refreshed)

    updated = skill_store.update(
        skill_id,
        user_id=str(user.id),
        enabled=payload.enabled,
        name=payload.name,
        description=payload.description,
        triggers=payload.triggers,
        allowed_tools=payload.allowed_tools,
        system_addendum=payload.system_addendum,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _skill_to_response(updated)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_skill(
    skill_id: str,
    user: CurrentUser,
    skill_store: SkillStore = Depends(get_skill_store),
) -> Response:
    if not skill_store.delete(skill_id, user_id=str(user.id)):
        raise HTTPException(status_code=404, detail="Skill not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assistants", response_model=AssistantListResponse)
async def list_assistants(
    user: CurrentUser,
    skill_catalog: SkillCatalog = Depends(get_skill_catalog),
) -> AssistantListResponse:
    assistants = [DEFAULT_ASSISTANT]
    for item in skill_catalog.list_for_user(str(user.id)):
        assistants.append(_assistant_to_response(item))
    return AssistantListResponse(assistants=assistants)


@router.post("/assistants", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    payload: AssistantCreate,
    user: CurrentUser,
    skill_store: SkillStore = Depends(get_skill_store),
) -> AssistantResponse:
    created = skill_store.create(
        user_id=str(user.id),
        name=payload.name,
        description=payload.description,
        triggers=payload.triggers,
        allowed_tools=payload.allowed_tools,
        system_addendum=payload.instructions,
        pick_only=payload.pick_only,
    )
    return _assistant_to_response(created)


@router.patch("/assistants/{assistant_id}", response_model=AssistantResponse)
async def update_assistant(
    assistant_id: str,
    payload: AssistantUpdate,
    user: CurrentUser,
    skill_catalog: SkillCatalog = Depends(get_skill_catalog),
    skill_store: SkillStore = Depends(get_skill_store),
) -> AssistantResponse:
    if assistant_id == "default":
        raise HTTPException(status_code=400, detail="The default assistant cannot be modified")

    current = skill_catalog.get_by_id(str(user.id), assistant_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Assistant not found")

    if current.bundled:
        if payload.enabled is None:
            return _assistant_to_response(current)
        skill_store.set_bundled_preference(str(user.id), assistant_id, enabled=payload.enabled)
        refreshed = skill_catalog.get_by_id(str(user.id), assistant_id)
        assert refreshed is not None
        return _assistant_to_response(refreshed)

    updated = skill_store.update(
        assistant_id,
        user_id=str(user.id),
        enabled=payload.enabled,
        name=payload.name,
        description=payload.description,
        triggers=payload.triggers,
        allowed_tools=payload.allowed_tools,
        system_addendum=payload.instructions,
        pick_only=payload.pick_only,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return _assistant_to_response(updated)


@router.delete("/assistants/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_assistant(
    assistant_id: str,
    user: CurrentUser,
    skill_store: SkillStore = Depends(get_skill_store),
) -> Response:
    if assistant_id == "default":
        raise HTTPException(status_code=400, detail="The default assistant cannot be deleted")
    if not skill_store.delete(assistant_id, user_id=str(user.id)):
        raise HTTPException(status_code=404, detail="Assistant not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks", response_model=AgentTaskListResponse)
async def list_tasks(
    user: CurrentUser,
    conversation_id: Optional[str] = Query(default=None),
    task_store: AgentTaskStore = Depends(get_agent_task_store),
) -> AgentTaskListResponse:
    tasks = [
        AgentTaskResponse.model_validate(task.__dict__)
        for task in task_store.list_for_user(str(user.id), conversation_id=conversation_id)
    ]
    return AgentTaskListResponse(tasks=tasks)


@router.post("/tasks", response_model=AgentTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: AgentTaskCreate,
    user: CurrentUser,
    task_store: AgentTaskStore = Depends(get_agent_task_store),
) -> AgentTaskResponse:
    task = task_store.create(
        user_id=str(user.id),
        title=payload.title,
        detail=payload.detail,
        conversation_id=payload.conversation_id,
        source="user",
    )
    return AgentTaskResponse.model_validate(task.__dict__)


@router.patch("/tasks/{task_id}", response_model=AgentTaskResponse)
async def update_task_status(
    task_id: str,
    payload: AgentTaskStatusUpdate,
    user: CurrentUser,
    task_store: AgentTaskStore = Depends(get_agent_task_store),
) -> AgentTaskResponse:
    task = task_store.update_status(task_id, user_id=str(user.id), status=payload.status)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTaskResponse.model_validate(task.__dict__)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_task(
    task_id: str,
    user: CurrentUser,
    task_store: AgentTaskStore = Depends(get_agent_task_store),
) -> Response:
    if not task_store.delete(task_id, user_id=str(user.id)):
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
