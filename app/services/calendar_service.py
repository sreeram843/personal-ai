"""Read-only calendar events from a public ICS feed (proof-of-pattern API connector)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import httpx

_EVENT_BLOCK = re.compile(r"BEGIN:VEVENT([\s\S]*?)END:VEVENT", re.IGNORECASE)
_FIELD = re.compile(r"^([A-Z-]+)(?:;[^:]*)?:(.*)$", re.MULTILINE)


def _parse_ics_datetime(raw: str) -> Optional[datetime]:
    value = (raw or "").strip()
    if not value:
        return None
    if re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
    normalized = value.replace("Z", "+0000")
    for fmt in ("%Y%m%dT%H%M%S%z", "%Y%m%dT%H%M%z"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _parse_events(ics_text: str) -> List[Tuple[str, datetime, Optional[datetime]]]:
    events: List[Tuple[str, datetime, Optional[datetime]]] = []
    for block in _EVENT_BLOCK.findall(ics_text or ""):
        fields: dict[str, str] = {}
        for match in _FIELD.finditer(block):
            key = match.group(1).upper()
            if key not in fields:
                fields[key] = match.group(2).strip()
        start = _parse_ics_datetime(fields.get("DTSTART", ""))
        if start is None:
            continue
        end = _parse_ics_datetime(fields.get("DTEND", ""))
        summary = fields.get("SUMMARY", "Untitled event")
        events.append((summary, start, end))
    events.sort(key=lambda item: item[1])
    return events


async def fetch_upcoming_events(
    ics_url: str,
    *,
    limit: int = 10,
    days_ahead: int = 14,
    timeout: float = 15.0,
) -> str:
    """Return a compact text block of upcoming calendar events."""
    if not ics_url.strip():
        return "ERROR: calendar ICS URL is not configured"

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(ics_url.strip())
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"ERROR: failed to fetch calendar feed: {exc}"

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days_ahead)
    events = _parse_events(response.text)
    upcoming = [event for event in events if now <= event[1] <= horizon][:limit]
    if not upcoming:
        return f"No upcoming events in the next {days_ahead} days."

    lines = [f"Upcoming calendar events (next {days_ahead} days):"]
    for summary, start, end in upcoming:
        start_label = start.strftime("%Y-%m-%d %H:%M UTC")
        if end is not None:
            end_label = end.strftime("%H:%M UTC")
            lines.append(f"- {summary}: {start_label} → {end_label}")
        else:
            lines.append(f"- {summary}: {start_label}")
    return "\n".join(lines)


__all__ = ["fetch_upcoming_events"]
