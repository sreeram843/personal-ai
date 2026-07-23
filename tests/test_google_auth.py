"""Tests for Google Sign-In authentication."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from tests.conftest import build_client


def test_auth_config_when_auth_disabled(client: TestClient) -> None:
    response = client.get("/auth/config")
    assert response.status_code == 200
    body = response.json()
    assert body["auth_disabled"] is True
    assert body["google_auth_enabled"] is False


def test_auth_config_when_google_enabled(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(
        update={"auth_disabled": False, "google_client_id": "test-client.apps.googleusercontent.com"},
    )
    client = build_client(db_session, settings)
    try:
        response = client.get("/auth/config")
        assert response.status_code == 200
        body = response.json()
        assert body["auth_disabled"] is False
        assert body["google_client_id"] == "test-client.apps.googleusercontent.com"
        assert body["google_auth_enabled"] is True
    finally:
        client.close()


def test_google_sign_in_creates_user_and_returns_token(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(
        update={
            "auth_disabled": False,
            "google_client_id": "test-client.apps.googleusercontent.com",
            "auth_signup_mode": "open",
        },
    )
    client = build_client(db_session, settings)
    claims = {
        "sub": "google-subject-123",
        "email": "alice@gmail.com",
        "name": "Alice Example",
    }
    try:
        with patch("app.api.auth_routes.verify_google_id_token", return_value=claims):
            response = client.post("/auth/google", json={"id_token": "fake-google-token"})

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me.status_code == 200
        profile = me.json()
        assert profile["email"] == "alice@gmail.com"
        assert profile["display_name"] == "Alice Example"
    finally:
        client.close()


def test_google_sign_in_rejected_when_auth_disabled(client: TestClient) -> None:
    response = client.post("/auth/google", json={"id_token": "fake-google-token"})
    assert response.status_code == 400


def test_google_sign_in_rejected_without_client_id(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(update={"auth_disabled": False, "google_client_id": None})
    client = build_client(db_session, settings)
    try:
        response = client.post("/auth/google", json={"id_token": "fake-google-token"})
        assert response.status_code == 503
    finally:
        client.close()
