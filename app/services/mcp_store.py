"""Per-user MCP server configuration (runtime connectors for chat tools)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class McpServerRecord:
    id: str
    user_id: str
    name: str
    url: str
    enabled: bool = True
    headers: Dict[str, str] | None = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    tool_count: int = 0
    last_checked_at: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "McpServerRecord":
        headers = raw.get("headers") or {}
        if not isinstance(headers, dict):
            headers = {}
        return cls(
            id=str(raw.get("id") or ""),
            user_id=str(raw.get("user_id") or ""),
            name=str(raw.get("name") or "MCP server"),
            url=str(raw.get("url") or ""),
            enabled=bool(raw.get("enabled", True)),
            headers={str(k): str(v) for k, v in headers.items()},
            last_status=raw.get("last_status"),
            last_error=raw.get("last_error"),
            tool_count=int(raw.get("tool_count") or 0),
            last_checked_at=raw.get("last_checked_at"),
        )


class McpServerStore:
    def __init__(self, *, file_path: str) -> None:
        self._path = Path(file_path)

    def list_for_user(self, user_id: str) -> List[McpServerRecord]:
        return [item for item in self._load_all() if item.user_id == user_id]

    def get(self, server_id: str, *, user_id: str) -> Optional[McpServerRecord]:
        for item in self._load_all():
            if item.id == server_id and item.user_id == user_id:
                return item
        return None

    def create(
        self,
        *,
        user_id: str,
        name: str,
        url: str,
        enabled: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ) -> McpServerRecord:
        record = McpServerRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name.strip(),
            url=url.strip(),
            enabled=enabled,
            headers={k.strip(): v for k, v in (headers or {}).items() if k.strip()},
        )
        items = self._load_all()
        items.append(record)
        self._write_all(items)
        return record

    def update(
        self,
        server_id: str,
        *,
        user_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        enabled: Optional[bool] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[McpServerRecord]:
        items = self._load_all()
        updated: Optional[McpServerRecord] = None
        for idx, item in enumerate(items):
            if item.id != server_id or item.user_id != user_id:
                continue
            if name is not None:
                item.name = name.strip()
            if url is not None:
                item.url = url.strip()
            if enabled is not None:
                item.enabled = enabled
            if headers is not None:
                item.headers = {k.strip(): v for k, v in headers.items() if k.strip()}
            items[idx] = item
            updated = item
            break
        if updated is None:
            return None
        self._write_all(items)
        return updated

    def delete(self, server_id: str, *, user_id: str) -> bool:
        items = self._load_all()
        next_items = [item for item in items if not (item.id == server_id and item.user_id == user_id)]
        if len(next_items) == len(items):
            return False
        self._write_all(next_items)
        return True

    def record_status(
        self,
        server_id: str,
        *,
        user_id: str,
        status: str,
        tool_count: int = 0,
        error: Optional[str] = None,
    ) -> None:
        items = self._load_all()
        for idx, item in enumerate(items):
            if item.id != server_id or item.user_id != user_id:
                continue
            item.last_status = status
            item.last_error = error
            item.tool_count = tool_count
            item.last_checked_at = _utc_now()
            items[idx] = item
            break
        self._write_all(items)

    def _load_all(self) -> List[McpServerRecord]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        return [McpServerRecord.from_dict(item) for item in raw if isinstance(item, dict)]

    def _write_all(self, items: List[McpServerRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items]
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_mcp_server_store(*, file_path: str) -> McpServerStore:
    return McpServerStore(file_path=file_path)


__all__ = ["McpServerRecord", "McpServerStore", "build_mcp_server_store"]
