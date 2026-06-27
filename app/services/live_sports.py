from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_LEAGUE_ALIASES = {
    "nba": "nba",
    "nfl": "nfl",
    "mlb": "mlb",
    "nhl": "nhl",
    "mls": "mls",
    "ncaaf": "ncaaf",
    "ncaab": "ncaab",
}

_SPORTS_HINTS = (
    "score",
    "scores",
    "scoreboard",
    "game",
    "match",
    "playing",
    "vs",
    "versus",
    "beat",
    "winning",
    "losing",
    "quarter",
    "inning",
    "innings",
    "period",
    "touchdown",
    "goal",
    "points",
    "wicket",
    "wickets",
    "overs",
    "run rate",
)

_CRICKET_HINTS = (
    "cricket",
    "ipl",
    "t20",
    "twenty20",
    "odi",
    "test match",
    "test cricket",
    "ashes",
    "bbl",
    "big bash",
    "asia cup",
    "world cup cricket",
    "cricinfo",
    "cricbuzz",
    "super over",
    "powerplay",
)

_CRICKET_LEAGUE_HINTS: dict[str, str] = {
    "ipl": "8048",
    "indian premier league": "8048",
    "big bash": "8044",
    "bbl": "8044",
    "world cup": "8039",
    "icc world cup": "8039",
    "t20 world cup": "8040",
    "champions trophy": "8037",
    "asia cup": "8532",
    "county championship": "8052",
    "t20 blast": "8053",
    "twenty20 cup": "8053",
}

_CRICKET_NATIONS = {
    "india",
    "australia",
    "england",
    "pakistan",
    "south africa",
    "new zealand",
    "sri lanka",
    "bangladesh",
    "west indies",
    "afghanistan",
    "ireland",
    "zimbabwe",
    "netherlands",
    "scotland",
    "usa",
    "united states",
    "nepal",
    "kenya",
    "uae",
    "united arab emirates",
}

_IPL_TEAM_HINTS = (
    "rcb",
    "mi",
    "csk",
    "kkr",
    "dc",
    "srh",
    "rr",
    "pbks",
    "gt",
    "lsg",
    "royal challengers",
    "mumbai indians",
    "chennai super kings",
    "kolkata knight riders",
    "delhi capitals",
    "sunrisers",
    "rajasthan royals",
    "punjab kings",
    "gujarat titans",
    "lucknow super giants",
)

_SOCCER_HINTS = (
    "soccer",
    "fifa",
    "uefa",
    "world cup",
    "euro ",
    "euro.",
    "nations league",
    "premier league",
    "la liga",
    "bundesliga",
    "serie a",
    "ligue 1",
    "champions league",
)

_AMERICAN_FOOTBALL_HINTS = (
    "nfl",
    "super bowl",
    "touchdown",
    "quarterback",
    "college football",
)

_NBA_TEAM_HINTS = (
    "lakers",
    "celtics",
    "warriors",
    "knicks",
    "nets",
    "bucks",
    "heat",
    "nuggets",
    "suns",
    "mavericks",
    "clippers",
    "bulls",
    "sixers",
    "76ers",
    "raptors",
    "spurs",
    "rockets",
    "thunder",
    "grizzlies",
    "pelicans",
    "timberwolves",
    "blazers",
    "kings",
    "jazz",
    "pistons",
    "pacers",
    "cavaliers",
    "cavs",
    "hawks",
    "hornets",
    "magic",
    "wizards",
)

_LEAGUE_PATTERN = re.compile(
    r"\b(nba|nfl|mlb|nhl|mls|ncaaf|ncaab|college football|college basketball)\b",
    re.IGNORECASE,
)

_VS_PATTERN = re.compile(
    r"(.+?)\s+(?:vs\.?|versus)\s+(.+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SportsGameQuery:
    league: str
    team_query: str
    opponent_query: Optional[str] = None


def detect_sports_game_query(query: str) -> Optional[SportsGameQuery]:
    """
    Return league + team match criteria when the user is asking for a live game score.

    Never defaults to NBA for ambiguous international/soccer queries.
    """
    text = query.strip()
    if not text:
        return None

    lower = text.lower()
    if not any(hint in lower for hint in _SPORTS_HINTS):
        return None

    team_a, team_b = _extract_matchup_teams(text)
    league = _infer_league(text, team_a=team_a, team_b=team_b)

    if league is None:
        return None

    team_query = team_a or _extract_team_query(text)
    if not team_query:
        return None

    return SportsGameQuery(league=league, team_query=team_query, opponent_query=team_b or None)


def _infer_league(text: str, *, team_a: str, team_b: str) -> Optional[str]:
    league_match = _LEAGUE_PATTERN.search(text)
    if league_match:
        token = league_match.group(1).lower().replace(" ", "")
        if token == "collegefootball":
            return "ncaaf"
        if token == "collegebasketball":
            return "ncaab"
        return _LEAGUE_ALIASES.get(token, token)

    lower = text.lower()

    if _looks_like_cricket(text, team_a=team_a, team_b=team_b):
        specific = _cricket_league_from_text(text)
        return f"cricket.{specific}" if specific else "cricket.intl"

    if _looks_like_international_soccer(text, team_a=team_a, team_b=team_b):
        return "soccer.intl"

    if any(hint in lower for hint in _AMERICAN_FOOTBALL_HINTS):
        return "nfl"

    if any(hint in lower for hint in _SOCCER_HINTS):
        return "soccer.intl"

    if any(hint in lower for hint in _NBA_TEAM_HINTS):
        return "nba"

    # Only default to NBA when the query looks like a US pro-sports score ask with a team fragment.
    if team_a and not team_b:
        return "nba"

    return None


def _looks_like_cricket(text: str, *, team_a: str, team_b: str) -> bool:
    lower = text.lower()
    if any(hint in lower for hint in _CRICKET_HINTS):
        return True
    if any(hint in lower for hint in _IPL_TEAM_HINTS):
        return True
    if team_a and team_b and _both_cricket_nations(team_a, team_b):
        return True
    return False


def _both_cricket_nations(team_a: str, team_b: str) -> bool:
    a = _normalize_team_token(team_a)
    b = _normalize_team_token(team_b)
    return a in _CRICKET_NATIONS and b in _CRICKET_NATIONS


def _normalize_team_token(name: str) -> str:
    token = name.strip().lower()
    token = re.sub(r"\s+(women|men)$", "", token)
    return token


def _cricket_league_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    for hint, league_id in sorted(_CRICKET_LEAGUE_HINTS.items(), key=lambda item: -len(item[0])):
        if hint in lower:
            return league_id
    return None


def _looks_like_international_soccer(text: str, *, team_a: str, team_b: str) -> bool:
    if _looks_like_cricket(text, team_a=team_a, team_b=team_b):
        return False
    lower = text.lower()
    if any(hint in lower for hint in _SOCCER_HINTS):
        return True

    if team_a and team_b:
        if re.search(r"\b(football|soccer)\b", lower) and not any(
            hint in lower for hint in _AMERICAN_FOOTBALL_HINTS
        ):
            return True
        # Two national-style names in a vs matchup — treat as soccer, not NBA.
        if not any(hint in lower for hint in _NBA_TEAM_HINTS):
            return True

    return False


def _extract_matchup_teams(text: str) -> tuple[str, str]:
    match = _VS_PATTERN.search(text)
    if not match:
        return "", ""

    left = _clean_team_fragment(match.group(1))
    right = _clean_team_fragment(match.group(2))
    return left, right


def _clean_team_fragment(fragment: str) -> str:
    cleaned = fragment.strip()
    cleaned = _LEAGUE_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(
        r"\b(what(?:'s| is)|how(?:'s| is)|current|latest|live|today(?:'s|)|"
        r"score|scores|scoreboard|game|match|the|for|of|in|on|right now|now|"
        r"football|soccer|cricket|ipl|nba|nfl|mlb|nhl|mls|t20|odi|wicket|overs)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" ?.,!")


def _extract_team_query(text: str) -> str:
    team_a, team_b = _extract_matchup_teams(text)
    if team_a:
        return team_a

    cleaned = text
    cleaned = _LEAGUE_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(
        r"\b(what(?:'s| is)|how(?:'s| is)|current|latest|live|today(?:'s|)|"
        r"score|scores|scoreboard|game|match|the|for|of|in|on|right now|now)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,!")
    return cleaned


__all__ = ["SportsGameQuery", "detect_sports_game_query"]
