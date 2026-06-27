from __future__ import annotations

from app.services.sports_data import SportsDataService


def _pick(events, team_query, opponent_query=None):
    service = SportsDataService()
    return service._pick_event(events, team_query, opponent_query)


def test_pick_event_requires_team_match_no_fallback() -> None:
    events = [
        {
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "New York Knicks"}, "score": "94"},
                        {"homeAway": "away", "team": {"displayName": "San Antonio Spurs"}, "score": "90"},
                    ]
                }
            ]
        }
    ]
    assert _pick(events, "Norway", "France") is None
    assert _pick(events, "Norway") is None


def test_pick_event_matches_both_soccer_teams() -> None:
    events = [
        {
            "id": "999",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Norway"}, "score": "1"},
                        {"homeAway": "away", "team": {"displayName": "France"}, "score": "2"},
                    ]
                }
            ]
        }
    ]
    matched = _pick(events, "Norway", "France")
    assert matched is not None
    assert matched["id"] == "999"


def test_competitor_score_parses_cricket_runs() -> None:
    from app.services.sports_data import _competitor_score

    display, numeric = _competitor_score({"score": "161/5 (18/20 ov, target 156)"})
    assert display.startswith("161/5")
    assert numeric == 161
