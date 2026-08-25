#!/usr/bin/env python3
"""Launch the stock-pred-model MCP HTTP server, or a compatible stub.

Prefers the sibling repo at ``<AI>/stock-pred-model/mcp/http_server.py``
(personal-ai's parent is ``AI/``). If that file is missing, serves the same
``get_forecast`` / ``get_chain`` / ``get_report`` tools and returns a
structured error on ``tools/call`` so CurieAI CI still works.

Usage:
    python scripts/mcp_stockpred.py --port 8765
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROTOCOL_VERSION = "2024-11-05"
TOOL_NAMES = ("get_forecast", "get_chain", "get_report")

_STUB_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_forecast",
        "description": "Probabilistic forecast for a symbol (CLI: stockpred forecast).",
        "inputSchema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}, "query": {"type": "string"}},
        },
    },
    {
        "name": "get_chain",
        "description": "Options chain / IV surface (CLI: stockpred chain).",
        "inputSchema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}, "query": {"type": "string"}},
        },
    },
    {
        "name": "get_report",
        "description": "Prediction-ledger scoreboard (CLI: stockpred report).",
        "inputSchema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}, "query": {"type": "string"}},
        },
    },
]


def sibling_server_path() -> Path:
    """``personal-ai/scripts`` → repo root → AI/ → stock-pred-model/mcp/http_server.py."""
    personal_ai_root = Path(__file__).resolve().parents[1]
    return personal_ai_root.parent / "stock-pred-model" / "mcp" / "http_server.py"


def load_sibling():
    path = sibling_server_path()
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("stockpred_mcp_http_server", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rpc_result(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _stub_call_error() -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    "stockpred CLI is not available. This is the CurieAI MCP stub "
                    "(sibling stock-pred-model/mcp/http_server.py was not found, or "
                    "STOCKPRED_MCP_STUB=1). tools/list still works; install stockpred "
                    "to run get_forecast / get_chain / get_report."
                ),
            }
        ],
        "isError": True,
    }


def handle_rpc_stub(body: Dict[str, Any]) -> Dict[str, Any]:
    request_id = body.get("id")
    method = str(body.get("method") or "")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    if method == "initialize":
        return _rpc_result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "stockpred-stub", "version": "0.1.0"},
            },
        )
    if method.startswith("notifications/") or method == "ping":
        return _rpc_result(request_id, {})
    if method == "tools/list":
        return _rpc_result(request_id, {"tools": _STUB_TOOLS})
    if method == "tools/call":
        name = str(params.get("name") or "").strip()
        if name not in TOOL_NAMES:
            return _rpc_result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True,
                },
            )
        return _rpc_result(request_id, _stub_call_error())
    return _rpc_error(request_id, -32601, f"Method not found: {method}")


class _StubHandler(BaseHTTPRequestHandler):
    server_version = "stockpred-mcp-stub/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {}
        if not isinstance(body, dict):
            body = {}
        session = self.headers.get("Mcp-Session-Id") or self.headers.get("mcp-session-id")
        if not session and str(body.get("method") or "") == "initialize":
            session = str(uuid.uuid4())
        payload = handle_rpc_stub(body)
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if session:
            self.send_header("Mcp-Session-Id", session)
        self.end_headers()
        self.wfile.write(data)


def start_stub_background(*, host: str = "127.0.0.1", port: int = 0) -> Tuple[ThreadingHTTPServer, int]:
    httpd = ThreadingHTTPServer((host, port), _StubHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, int(httpd.server_address[1])


def start_background(*, host: str = "127.0.0.1", port: int = 0) -> Tuple[ThreadingHTTPServer, int]:
    sibling = load_sibling()
    if sibling is not None and hasattr(sibling, "start_background"):
        return sibling.start_background(host=host, port=port)
    return start_stub_background(host=host, port=port)


def serve(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    sibling = load_sibling()
    if sibling is not None and hasattr(sibling, "serve"):
        print(f"using sibling server {sibling_server_path()}", flush=True)
        sibling.serve(host=host, port=port)
        return
    httpd = ThreadingHTTPServer((host, port), _StubHandler)
    print(
        f"stockpred MCP stub on http://{host}:{port}/  (sibling server not found; tools still list)",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        httpd.server_close()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="stockpred MCP HTTP server (sibling or stub)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
