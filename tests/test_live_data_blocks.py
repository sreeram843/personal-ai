from app.schemas.adapter import AdapterResult
from app.services.live_data_manager import LiveDataManager
from app.services.live_sports import detect_sports_game_query


def test_detect_sports_game_query_nba_team() -> None:
    detected = detect_sports_game_query("What's the Lakers score right now?")
    assert detected is not None
    assert detected.league == "nba"
    assert "lakers" in detected.team_query.lower()


def test_detect_sports_game_query_cricket_ipl() -> None:
    detected = detect_sports_game_query("RCB vs GT IPL score")
    assert detected is not None
    assert detected.league == "cricket.8048"
    assert "rcb" in detected.team_query.lower()
    assert detected.opponent_query and "gt" in detected.opponent_query.lower()


def test_detect_sports_game_query_cricket_international() -> None:
    detected = detect_sports_game_query("India vs Australia cricket score")
    assert detected is not None
    assert detected.league == "cricket.intl"
    assert detected.team_query.lower() == "india"
    assert detected.opponent_query and detected.opponent_query.lower() == "australia"


def test_detect_sports_game_query_international_soccer() -> None:
    detected = detect_sports_game_query("Norway vs France football game")
    assert detected is not None
    assert detected.league == "soccer.intl"
    assert detected.team_query.lower() == "norway"
    assert detected.opponent_query and detected.opponent_query.lower() == "france"

    detected_soccer = detect_sports_game_query("Norway vs France soccer game")
    assert detected_soccer is not None
    assert detected_soccer.league == "soccer.intl"


def test_detect_sports_game_query_does_not_default_nba_for_countries() -> None:
    detected = detect_sports_game_query("Brazil vs Argentina match")
    assert detected is not None
    assert detected.league == "soccer.intl"
    assert detected.league != "nba"


def test_to_blocks_stock() -> None:
    result = AdapterResult(
        domain="stock",
        status="ok",
        verified=True,
        source="Yahoo Finance",
        fetched_at_utc="2026-06-26 12:00:00 UTC",
        data={
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "price": 201.5,
            "currency": "USD",
            "change": 1.2,
            "change_percent": 0.6,
            "previous_close": 200.3,
            "exchange": "NASDAQ",
            "market_state": "REGULAR",
        },
    )
    blocks = LiveDataManager.to_blocks(result)
    assert len(blocks) == 1
    assert blocks[0].type == "stock"
    assert blocks[0].data["ticker"] == "AAPL"
    assert blocks[0].data["live"] is True


def test_to_blocks_game_score() -> None:
    result = AdapterResult(
        domain="game_score",
        status="ok",
        verified=True,
        source="ESPN Scoreboard",
        fetched_at_utc="2026-06-26 12:00:00 UTC",
        data={
            "league": "NBA",
            "home_team": "Los Angeles Lakers",
            "away_team": "Boston Celtics",
            "home_score": 102,
            "away_score": 99,
            "status": "Q4 - 2:14",
            "is_live": True,
            "subscription_key": "sports:nba:401585673",
        },
    )
    blocks = LiveDataManager.to_blocks(result)
    assert len(blocks) == 1
    assert blocks[0].type == "game_score"
    assert blocks[0].subscription_key == "sports:nba:401585673"
    assert blocks[0].data["isLive"] is True
