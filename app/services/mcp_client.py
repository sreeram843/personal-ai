"""Lightweight MCP HTTP client (streamable HTTP / JSON-RPC over httpx)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"


@dataclass
class McpToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]


class McpHttpClient:
    """Connect to a remote MCP server over HTTP (JSON-RPC, streamable HTTP transport)."""

    def __init__(
        self,
        *,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 20.0,
    ) -> None:
        self.url = url.strip()
        self.headers = {k: v for k, v in (headers or {}).items() if k.strip()}
        self.timeout = timeout
        self._request_id = 0
        self._session_id: Optional[str] = None
        self._initialized = False

    async def connect(self) -> None:
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "personal-ai", "version": "1.0.0"},
            },
        )
        if result.get("error"):
            raise RuntimeError(str(result["error"]))
        await self._rpc("notifications/initialized", {})
        self._initialized = True

    async def list_tools(self) -> List[McpToolDefinition]:
        if not self._initialized:
            await self.connect()
        result = await self._rpc("tools/list", {})
        if result.get("error"):
            raise RuntimeError(str(result["error"]))
        tools_raw = (result.get("result") or {}).get("tools") or []
        tools: List[McpToolDefinition] = []
        for item in tools_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            tools.append(
                McpToolDefinition(
                    name=name,
                    description=str(item.get("description") or "").strip() or f"MCP tool {name}",
                    input_schema=item.get("inputSchema") if isinstance(item.get("inputSchema"), dict) else {},
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        if not self._initialized:
            await self.connect()
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("error"):
            raise RuntimeError(str(result["error"]))
        payload = result.get("result") or {}
        content = payload.get("content") or []
        parts: List[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        if payload.get("isError"):
            raise RuntimeError("\n".join(parts) or "MCP tool returned an error")
        return "\n".join(part for part in parts if part.strip()).strip() or "(empty MCP response)"

    async def _rpc(self, method: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        self._request_id += 1
        body: Dict[str, Any] = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params is not None:
            body["params"] = params
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.post(self.url, json=body, headers=headers)
            response.raise_for_status()
            session_header = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
            if session_header:
                self._session_id = session_header
            return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/event-stream" in content_type:
            return self._parse_sse_payload(response.text)
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid MCP JSON response: {response.text[:200]}") from exc
        if isinstance(data, dict):
            return data
        raise RuntimeError("Unexpected MCP response shape")

    @staticmethod
    def _parse_sse_payload(text: str) -> Dict[str, Any]:
        for line in reversed(text.splitlines()):
            cleaned = line.strip()
            if not cleaned.startswith("data:"):
                continue
            payload = cleaned[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise RuntimeError("MCP SSE response did not contain JSON data")


__all__ = ["McpHttpClient", "McpToolDefinition"]
