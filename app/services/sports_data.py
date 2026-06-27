from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

ESPN_LEAGUE_PATHS = {
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "mls": "soccer/usa.1",
    "ncaaf": "football/college-football",
    "ncaab": "basketball/mens-college-basketball",
}

# Searched in order when league is soccer.intl (national/club soccer).
INTERNATIONAL_SOCCER_PATHS = [
    "soccer/uefa.nations",
    "soccer/fifa.friendly",
    "soccer/uefa.euro",
    "soccer/fifa.world",
    "soccer/uefa.champions",
    "soccer/eng.1",
    "soccer/esp.1",
    "soccer/ger.1",
    "soccer/ita.1",
    "soccer/fra.1",
    "soccer/usa.1",
]

# ESPN cricket scoreboards use numeric league IDs (not slug paths).
CRICKET_LEAGUE_IDS: dict[str, str] = {
    "8048": "Indian Premier League",
    "8044": "Big Bash League",
    "8039": "World Cup",
    "8037": "ICC Champions Trophy",
    "8040": "ICC Men's T20 World Cup Qualifier",
    "8532": "Men's T20 Asia Cup",
    "8053": "Twenty20 Cup (England)",
    "8052": "County Championship Division One",
    "8082": "Champions League Twenty20",
    "8050": "Ranji Trophy",
}

CRICKET_SEARCH_PATHS = [f"cricket/{league_id}" for league_id in CRICKET_LEAGUE_IDS]

LIVE_STATUS_CODES = {"in", "live", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30"}


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _team_matches(team: dict, query: str) -> bool:
    needle = _normalize(query)
    if not needle:
        return False
    candidates = [
        team.get("displayName", ""),
        team.get("shortDisplayName", ""),
        team.get("abbreviation", ""),
        team.get("name", ""),
        team.get("location", ""),
    ]
    for candidate in candidates:
        token = _normalize(str(candidate))
        if not token:
            continue
        if token == needle or token in needle or needle in token:
            return True
    return False


def _split_matchup_query(team_query: str) -> tuple[str, Optional[str]]:
    match = re.search(r"(.+?)\s+(?:vs\.?|versus)\s+(.+)", team_query, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return team_query.strip(), None


def _parse_competitors(event: dict) -> tuple[dict, dict, int, int, str, str]:
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    home = next((item for item in competitors if item.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((item for item in competitors if item.get("homeAway") == "away"), competitors[-1] if len(competitors) > 1 else {})
    home_team = home.get("team") or {}
    away_team = away.get("team") or {}
    home_display, home_numeric = _competitor_score(home)
    away_display, away_numeric = _competitor_score(away)
    return home_team, away_team, home_numeric, away_numeric, home_display, away_display


def _competitor_score(competitor: dict) -> tuple[str, int]:
    raw = competitor.get("score")
    if isinstance(raw, str) and raw.strip():
        numeric = 0
        head = raw.split("(", 1)[0].strip()
        if "/" in head:
            runs_part = head.split("/", 1)[0]
            try:
                numeric = int(runs_part.strip())
            except ValueError:
                numeric = 0
        return raw.strip(), numeric
    try:
        numeric = int(raw or 0)
    except (TypeError, ValueError):
        numeric = 0
    return str(numeric), numeric


def _is_cricket_event(event: dict) -> bool:
    competition = (event.get("competitions") or [{}])[0]
    event_class = competition.get("class") or {}
    if str(event_class.get("eventType") or "").upper() in {"T20", "ODI", "TEST"}:
        return True
    if "cricket" in str(event_class.get("name") or "").lower():
        return True
    competitors = competition.get("competitors") or []
    for competitor in competitors:
        score = competitor.get("score")
        if isinstance(score, str) and ("/" in score or "ov" in score.lower()):
            return True
    return False


def _cricket_is_live(event: dict) -> bool:
    _, _, _, is_live_default = _event_status(event)
    if is_live_default:
        return True
    competition = (event.get("competitions") or [{}])[0]
    status = competition.get("status") or event.get("status") or {}
    state = str((status.get("type") or {}).get("state") or "").lower()
    if state in {"in", "live"}:
        return True
    for competitor in competition.get("competitors") or []:
        for line in competitor.get("linescores") or []:
            if line.get("isCurrent") or line.get("isBatting"):
                return True
    return False


def _event_status(event: dict) -> tuple[str, str, str, bool]:
    competition = (event.get("competitions") or [{}])[0]
    status = competition.get("status") or event.get("status") or {}
    status_type = status.get("type") or {}
    state = str(status_type.get("state") or status_type.get("name") or "").lower()
    detail = str(status_type.get("detail") or status_type.get("shortDetail") or status_type.get("description") or "Scheduled")
    short = str(status_type.get("shortDetail") or detail)
    period = str(status.get("period") or "")
    clock = str(status.get("displayClock") or "")
    is_live = state == "in" or "progress" in state or detail.lower().startswith("q") or "in progress" in detail.lower()
    return detail, period, clock, is_live


class SportsDataService:
    """Fetch structured scoreboard data from ESPN's public scoreboard API."""

    def __init__(self, *, timeout: float = 12.0) -> None:
        self._timeout = timeout

    async def fetch_game_for_team(
        self,
        league: str,
        team_query: str,
        *,
        opponent_query: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        league_key = league.lower()
        opponent = opponent_query.strip() if opponent_query else None
        primary, parsed_opponent = _split_matchup_query(team_query)
        if not opponent and parsed_opponent:
            opponent = parsed_opponent
        team_query = primary or team_query

        if league_key == "soccer.intl":
            return await self._fetch_international_soccer_match(team_query, opponent)

        if league_key.startswith("cricket"):
            return await self._fetch_cricket_match(league_key, team_query, opponent)

        path = ESPN_LEAGUE_PATHS.get(league_key)
        if not path:
            return None

        payload = await self._fetch_scoreboard(path)
        if payload is None:
            return None

        events: List[dict] = payload.get("events") or []
        matched = self._pick_event(events, team_query, opponent)
        if matched is None:
            return None

        return self._normalize_event(league_key, matched, payload.get("leagues") or [])

    async def _fetch_international_soccer_match(
        self,
        team_query: str,
        opponent_query: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        for path in INTERNATIONAL_SOCCER_PATHS:
            payload = await self._fetch_scoreboard(path)
            if payload is None:
                continue
            events: List[dict] = payload.get("events") or []
            matched = self._pick_event(events, team_query, opponent_query)
            if matched is None:
                continue
            league_key = path.split("/", 1)[-1].replace(".", "_")
            return self._normalize_event(league_key, matched, payload.get("leagues") or [], source_path=path)
        return None

    async def _fetch_cricket_match(
        self,
        league_key: str,
        team_query: str,
        opponent_query: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        paths = list(CRICKET_SEARCH_PATHS)
        if league_key.startswith("cricket.") and league_key != "cricket.intl":
            league_id = league_key.split(".", 1)[1]
            paths = [f"cricket/{league_id}"]

        for path in paths:
            payload = await self._fetch_scoreboard(path)
            if payload is None:
                continue
            events: List[dict] = payload.get("events") or []
            matched = self._pick_event(events, team_query, opponent_query)
            if matched is None:
                continue
            return self._normalize_event(
                path.split("/", 1)[-1],
                matched,
                payload.get("leagues") or [],
                source_path=path,
                sport="cricket",
            )
        return None

    async def _fetch_scoreboard(self, path: str) -> Optional[dict]:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; personal-ai-bot/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("Sports scoreboard fetch failed for path=%s: %s", path, exc)
            return None

    async def fetch_event_by_id(self, league: str, event_id: str) -> Optional[Dict[str, Any]]:
        league_key = league.strip()
        path = ESPN_LEAGUE_PATHS.get(league_key.lower())
        if not path:
            if "/" in league_key:
                path = league_key
            else:
                for candidate in INTERNATIONAL_SOCCER_PATHS:
                    if league_key.lower() in candidate.lower():
                        path = candidate
                        break
                if path is None:
                    for candidate in CRICKET_SEARCH_PATHS:
                        if league_key.lower() in candidate.lower():
                            path = candidate
                            break
        if not path or not event_id.strip():
            return None

        payload = await self._fetch_scoreboard(path)
        if payload is None:
            return None

        target_id = str(event_id).strip()
        for event in payload.get("events") or []:
            if str(event.get("id") or "") == target_id:
                sport = "cricket" if str(path).startswith("cricket/") else None
                return self._normalize_event(
                    league_key,
                    event,
                    payload.get("leagues") or [],
                    source_path=path,
                    sport=sport,
                )
        return None

    def _pick_event(
        self,
        events: List[dict],
        team_query: str,
        opponent_query: Optional[str] = None,
    ) -> Optional[dict]:
        if not events:
            return None
        query = team_query.strip()
        if not query:
            return None

        if opponent_query and opponent_query.strip():
            for event in events:
                if self._event_matches_teams(event, query, opponent_query.strip()):
                    return event
            return None

        for event in events:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            for competitor in competitors:
                team = competitor.get("team") or {}
                if _team_matches(team, query):
                    return event
        return None

    def _event_matches_teams(self, event: dict, team_a: str, team_b: str) -> bool:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        teams = [competitor.get("team") or {} for competitor in competitors]
        if len(teams) < 2:
            return False
        a_match = any(_team_matches(team, team_a) for team in teams)
        b_match = any(_team_matches(team, team_b) for team in teams)
        return a_match and b_match

    def _normalize_event(
        self,
        league: str,
        event: dict,
        leagues: List[dict],
        *,
        source_path: Optional[str] = None,
        sport: Optional[str] = None,
    ) -> Dict[str, Any]:
        home_team, away_team, home_score, away_score, home_display, away_display = _parse_competitors(event)
        status_detail, period, clock, is_live = _event_status(event)
        is_cricket = sport == "cricket" or _is_cricket_event(event)
        if is_cricket:
            is_live = _cricket_is_live(event)
        league_label = league.upper()
        if leagues:
            league_label = str((leagues[0] or {}).get("abbreviation") or (leagues[0] or {}).get("name") or league_label)
        competition = (event.get("competitions") or [{}])[0]
        event_class = competition.get("class") or {}
        match_format = str(event_class.get("eventType") or event_class.get("generalClassCard") or "")
        venue = str(((competition.get("venue") or {}).get("fullName")) or "")

        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        event_id = str(event.get("id") or "")
        storage_league = source_path or ESPN_LEAGUE_PATHS.get(league.lower(), league.lower())
        payload = {
            "league": league_label,
            "league_key": storage_league,
            "event_id": event_id,
            "home_team": home_team.get("displayName") or home_team.get("shortDisplayName") or "Home",
            "away_team": away_team.get("displayName") or away_team.get("shortDisplayName") or "Away",
            "home_abbrev": home_team.get("abbreviation") or "",
            "away_abbrev": away_team.get("abbreviation") or "",
            "home_score": home_score,
            "away_score": away_score,
            "status": status_detail,
            "period": period,
            "clock": clock,
            "is_live": is_live,
            "start_time": event.get("date") or "",
            "source": "ESPN Scoreboard",
            "fetched_at_utc": fetched_at,
            "subscription_key": f"sports:{storage_league}:{event_id}" if event_id else None,
        }
        if is_cricket:
            payload.update(
                {
                    "sport": "cricket",
                    "home_score_display": home_display,
                    "away_score_display": away_display,
                    "match_format": match_format,
                    "venue": venue,
                }
            )
        return payload


__all__ = ["SportsDataService", "ESPN_LEAGUE_PATHS"]
