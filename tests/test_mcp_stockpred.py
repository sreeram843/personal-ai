"""HTTP MCP wrapper for stock-pred-model (issue #42)."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

from app.schemas.tool import ToolCapability, ToolRiskClass, ToolSpec
from app.services.mcp_client import McpHttpClient
from app.services.mcp_tools import _risk_for_mcp_tool, mcp_tool_id
from app.services.tool_permissions import tool_requires_user_approval

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "mcp_stockpred.py"
EXPECTED_TOOLS = {"get_forecast", "get_chain", "get_report"}


def _load_launcher():
    spec = importlib.util.spec_from_file_location("mcp_stockpred_launcher", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stockpred_mcp_url():
    launcher = _load_launcher()
    httpd, port = launcher.start_background(host="127.0.0.1", port=0)
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_mcp_stockpred_lists_and_calls_forecast(stockpred_mcp_url: str) -> None:
    async def _run() -> None:
        client = McpHttpClient(url=stockpred_mcp_url, timeout=8.0)
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert EXPECTED_TOOLS <= names
        try:
            text = await client.call_tool("get_forecast", {"symbol": "DUMMY"})
        except RuntimeError as exc:
            text = str(exc)
        assert text.strip()
        assert "stockpred" in text.lower()

    asyncio.run(_run())


def test_mcp_get_forecast_is_read_ish_for_approval() -> None:
    """get_* names match mcp_tools / tool_permissions read heuristics."""
    tool_id = mcp_tool_id("stockpredtest", "get_forecast")
    risk, requires_approval = _risk_for_mcp_tool(
        "get_forecast",
        "Probabilistic forecast (CLI: stockpred forecast).",
    )
    assert risk == ToolRiskClass.NETWORK
    assert requires_approval is False
    spec = ToolSpec(
        tool_id=tool_id,
        name="stockpred: get_forecast",
        description="[MCP:stockpred] Probabilistic forecast",
        risk_class=risk,
        capabilities={ToolCapability.NETWORK_REQUEST},
        allowed_roles={"chat_agent"},
        requires_approval=requires_approval,
    )
    assert tool_requires_user_approval(tool_id, spec) is False

    report_id = mcp_tool_id("stockpredtest", "get_report")
    report_risk, report_approval = _risk_for_mcp_tool("get_report", "Ledger scoreboard")
    assert report_risk == ToolRiskClass.NETWORK
    assert report_approval is False
    report_spec = ToolSpec(
        tool_id=report_id,
        name="stockpred: get_report",
        description="[MCP:stockpred] report",
        risk_class=report_risk,
        capabilities={ToolCapability.NETWORK_REQUEST},
        allowed_roles={"chat_agent"},
        requires_approval=report_approval,
    )
    assert tool_requires_user_approval(report_id, report_spec) is False


def test_mcp_write_like_tool_requires_approval() -> None:
    """Write-shaped MCP names still go through tool_requires_user_approval."""
    tool_id = mcp_tool_id("stockpredtest", "create_issue")
    risk, requires_approval = _risk_for_mcp_tool("create_issue", "Creates a GitHub issue")
    assert risk == ToolRiskClass.NETWORK
    assert requires_approval is True
    spec = ToolSpec(
        tool_id=tool_id,
        name="stockpred: create_issue",
        description="[MCP:stockpred] Creates a GitHub issue",
        risk_class=risk,
        capabilities={ToolCapability.NETWORK_REQUEST},
        allowed_roles={"chat_agent"},
        requires_approval=requires_approval,
    )
    assert tool_id.startswith("mcp_")
    assert tool_requires_user_approval(tool_id, spec) is True


def test_bare_forecast_name_would_need_approval() -> None:
    """Without get_, 'forecast' is unknown NETWORK and may need ask-mode approval."""
    tool_id = mcp_tool_id("stockpredtest", "forecast")
    risk, requires_approval = _risk_for_mcp_tool("forecast", "Run a forecast")
    assert risk == ToolRiskClass.NETWORK
    spec = ToolSpec(
        tool_id=tool_id,
        name="stockpred: forecast",
        description="[MCP:stockpred] Run a forecast",
        risk_class=risk,
        capabilities={ToolCapability.NETWORK_REQUEST},
        allowed_roles={"chat_agent"},
        requires_approval=requires_approval,
    )
    assert tool_requires_user_approval(tool_id, spec) is True
