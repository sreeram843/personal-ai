from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.live_data_manager import LiveDataManager


@pytest.mark.asyncio
async def test_refresh_block_sports_subscription() -> None:
    sports = AsyncMock()
    sports.fetch_event_by_id.return_value = {
        "league": "NBA",
        "league_key": "nba",
        "event_id": "401585673",
        "home_team": "Los Angeles Lakers",
        "away_team": "Boston Celtics",
        "home_abbrev": "LAL",
        "away_abbrev": "BOS",
        "home_score": 104,
        "away_score": 101,
        "status": "Q4 - 1:02",
        "period": "4",
        "clock": "1:02",
        "is_live": True,
        "source": "ESPN Scoreboard",
        "fetched_at_utc": "2026-06-26 12:00:00 UTC",
        "subscription_key": "sports:nba:401585673",
    }
    manager = LiveDataManager(web_search=MagicMock(), cache=MagicMock(), settings=MagicMock(), sports=sports)

    block = await manager.refresh_block("sports:nba:401585673")
    assert block is not None
    assert block.type == "game_score"
    assert block.data["homeScore"] == 104
    assert block.subscription_key == "sports:nba:401585673"
    sports.fetch_event_by_id.assert_awaited_once_with("nba", "401585673")


@pytest.mark.asyncio
async def test_refresh_block_unknown_key() -> None:
    manager = LiveDataManager(web_search=MagicMock(), cache=MagicMock(), settings=MagicMock())
    assert await manager.refresh_block("unknown:key") is None
