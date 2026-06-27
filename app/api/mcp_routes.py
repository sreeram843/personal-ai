"""Runtime MCP connector management for chat tools."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.core.auth import CurrentUser
from app.core.deps import get_mcp_server_store
from app.schemas.agent import (
    McpServerCreate,
    McpServerListResponse,
    McpServerResponse,
    McpServerTestResponse,
    McpServerUpdate,
)
from app.services.mcp_client import McpHttpClient
from app.services.mcp_store import McpServerStore

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _to_response(record) -> McpServerResponse:
    return McpServerResponse(
        id=record.id,
        name=record.name,
        url=record.url,
        enabled=record.enabled,
        header_keys=sorted((record.headers or {}).keys()),
        last_status=record.last_status,
        last_error=record.last_error,
        tool_count=record.tool_count,
        last_checked_at=record.last_checked_at,
    )


@router.get("/servers", response_model=McpServerListResponse)
async def list_mcp_servers(
    user: CurrentUser,
    store: McpServerStore = Depends(get_mcp_server_store),
) -> McpServerListResponse:
    servers = [_to_response(item) for item in store.list_for_user(str(user.id))]
    return McpServerListResponse(servers=servers)


@router.post("/servers", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    payload: McpServerCreate,
    user: CurrentUser,
    store: McpServerStore = Depends(get_mcp_server_store),
) -> McpServerResponse:
    record = store.create(
        user_id=str(user.id),
        name=payload.name,
        url=payload.url,
        enabled=payload.enabled,
        headers=payload.headers,
    )
    return _to_response(record)


@router.patch("/servers/{server_id}", response_model=McpServerResponse)
async def update_mcp_server(
    server_id: str,
    payload: McpServerUpdate,
    user: CurrentUser,
    store: McpServerStore = Depends(get_mcp_server_store),
) -> McpServerResponse:
    record = store.update(
        server_id,
        user_id=str(user.id),
        name=payload.name,
        url=payload.url,
        enabled=payload.enabled,
        headers=payload.headers,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return _to_response(record)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_mcp_server(
    server_id: str,
    user: CurrentUser,
    store: McpServerStore = Depends(get_mcp_server_store),
) -> Response:
    deleted = store.delete(server_id, user_id=str(user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/servers/{server_id}/test", response_model=McpServerTestResponse)
async def test_mcp_server(
    server_id: str,
    user: CurrentUser,
    store: McpServerStore = Depends(get_mcp_server_store),
) -> McpServerTestResponse:
    record = store.get(server_id, user_id=str(user.id))
    if record is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    client = McpHttpClient(url=record.url, headers=record.headers or {})
    try:
        tools = await client.list_tools()
        names = [tool.name for tool in tools]
        store.record_status(record.id, user_id=str(user.id), status="connected", tool_count=len(names))
        return McpServerTestResponse(ok=True, tool_count=len(names), tools=names[:40])
    except Exception as exc:
        message = str(exc)
        store.record_status(record.id, user_id=str(user.id), status="error", tool_count=0, error=message)
        return McpServerTestResponse(ok=False, error=message)


__all__ = ["router"]
