"""Structured audit events for auth and data mutations (Loki-queryable)."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("personal_ai.audit")


def record_audit(
    event: str,
    *,
    user_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    """Emit a single JSON audit line for Grafana Loki / ops review."""
    payload: dict[str, Any] = {
        "audit_event": event,
        "user_id": user_id,
        "detail": detail or {},
    }
    logger.info("%s", json.dumps(payload, default=str, separators=(",", ":")))
