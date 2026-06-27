from app.services.calendar_service import fetch_upcoming_events, _parse_events


SAMPLE_ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Team standup
DTSTART:20260627T100000Z
DTEND:20260627T103000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Past event
DTSTART:20260101T100000Z
END:VEVENT
END:VCALENDAR
"""


def test_parse_ics_events_sorts_by_start():
    events = _parse_events(SAMPLE_ICS)
    assert len(events) == 2
    assert events[0][0] == "Past event"
    assert events[1][0] == "Team standup"
