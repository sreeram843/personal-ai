"""Optional live smoke tests for OAuth wiring (run against a running server).

Usage:
  OAUTH_LIVE_TEST=1 pytest tests/test_oauth_live.py -q --no-cov

Requires the app to be running with AUTH_DISABLED=false and GOOGLE_CLIENT_ID set.
"""

from __future__ import annotations

import os

import httpx
import pytest

LIVE = os.getenv("OAUTH_LIVE_TEST", "").lower() in {"1", "true", "yes"}
BASE_URL = os.getenv("OAUTH_LIVE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


pytestmark = pytest.mark.skipif(not LIVE, reason="Set OAUTH_LIVE_TEST=1 to run live OAuth smoke tests")


def test_auth_config_reports_google_enabled() -> None:
    response = httpx.get(f"{BASE_URL}/auth/config", timeout=10.0)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["auth_disabled"] is False
    assert body["google_auth_enabled"] is True
    assert body["google_client_id"] and body["google_client_id"].endswith(".apps.googleusercontent.com")


def test_unauthenticated_me_returns_401() -> None:
    response = httpx.get(f"{BASE_URL}/auth/me", timeout=10.0)
    assert response.status_code == 401


def test_unauthenticated_conversations_returns_401() -> None:
    response = httpx.get(f"{BASE_URL}/conversations", timeout=10.0)
    assert response.status_code == 401


def test_google_endpoint_rejects_invalid_token() -> None:
    response = httpx.post(
        f"{BASE_URL}/auth/google",
        json={"id_token": "not-a-valid-google-id-token"},
        timeout=10.0,
    )
    assert response.status_code in {401, 400}
