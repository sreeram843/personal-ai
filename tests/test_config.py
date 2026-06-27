"""Config flag tests for tool agent."""

from app.core.config import Settings


def test_enable_tool_agent_reads_legacy_langchain_alias() -> None:
    settings = Settings(enable_langchain_agent=False)
    assert settings.enable_tool_agent is False
