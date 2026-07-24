"""Tests for admin auth gates, secret box, and admin APIs."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import create_invite, get_or_create_user_by_google
from app.core.config import Settings
from app.core.security import create_access_token
from app.db.models import User, UserRole
from app.services.secret_box import decrypt_secret, encrypt_secret, key_last4
from app.services.settings_store import clear_settings_cache
from tests.conftest import build_client


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_encrypt_roundtrip() -> None:
    settings = Settings(settings_secret_key="unit-test-secret", jwt_secret="x")
    cipher = encrypt_secret("gsk_test_secret_value", settings)
    assert cipher != "gsk_test_secret_value"
    assert decrypt_secret(cipher, settings) == "gsk_test_secret_value"
    assert key_last4("gsk_test_secret_value") == "alue"


def test_auth_token_disabled_when_auth_enabled(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(update={"auth_disabled": False})
    client = build_client(db_session, settings)
    try:
        response = client.post("/auth/token", json={"email": "anyone@example.com"})
        assert response.status_code == 403
    finally:
        client.close()


def test_invite_only_blocks_unknown_google_user(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(
        update={"auth_disabled": False, "auth_signup_mode": "invite", "admin_emails": ""},
    )
    with pytest.raises(PermissionError):
        get_or_create_user_by_google(
            db_session,
            sub="google-sub-1",
            email="stranger@example.com",
            display_name="Stranger",
            settings=settings,
        )


def test_invite_allows_google_signup(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(
        update={"auth_disabled": False, "auth_signup_mode": "invite", "admin_emails": ""},
    )
    create_invite(db_session, email="friend@example.com", role=UserRole.user.value)
    user = get_or_create_user_by_google(
        db_session,
        sub="google-sub-2",
        email="friend@example.com",
        display_name="Friend",
        settings=settings,
    )
    assert user.email == "friend@example.com"
    assert user.role == UserRole.user.value


def _admin_client(db_session, auth_settings: Settings) -> tuple[TestClient, User, Settings]:
    settings = auth_settings.model_copy(
        update={
            "auth_disabled": False,
            "settings_secret_key": "test-settings-secret",
            "admin_emails": "admin@example.com",
            "auth_signup_mode": "invite",
            "google_client_id": "test-client",
        }
    )
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin",
        role=UserRole.admin.value,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    client = build_client(db_session, settings)
    token = create_access_token(user_id=admin.id, settings=settings)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, admin, settings


def test_admin_providers_hide_api_key(db_session, auth_settings: Settings) -> None:
    client, _admin, _settings = _admin_client(db_session, auth_settings)
    try:
        created = client.post(
            "/admin/providers",
            json={
                "name": "groq",
                "display_name": "Groq",
                "base_url": "https://api.groq.com/openai",
                "api_key": "gsk_super_secret_key_1234",
                "enabled": True,
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["has_key"] is True
        assert body["key_last4"] == "1234"
        assert "api_key" not in body

        listed = client.get("/admin/providers")
        assert listed.status_code == 200
        assert listed.json()[0]["has_key"] is True
    finally:
        client.close()


def test_admin_signup_mode_and_usage(db_session, auth_settings: Settings) -> None:
    client, _admin, _settings = _admin_client(db_session, auth_settings)
    try:
        mode = client.put("/admin/signup-mode", json={"mode": "open"})
        assert mode.status_code == 200
        assert mode.json()["mode"] == "open"

        summary = client.get("/admin/usage/summary?days=7")
        assert summary.status_code == 200
        assert "total_tokens" in summary.json()
        assert "series" in summary.json()
    finally:
        client.close()


def test_admin_routing_rejects_unknown_provider(db_session, auth_settings: Settings) -> None:
    client, _admin, _settings = _admin_client(db_session, auth_settings)
    try:
        response = client.put(
            "/admin/routing",
            json={
                "default_provider": "missing_vendor",
                "default_model": "x",
                "planner_provider": "ollama",
                "planner_model": "x",
                "synthesizer_provider": "ollama",
                "synthesizer_model": "x",
                "reviewer_provider": "ollama",
                "reviewer_model": "x",
                "writer_provider": "ollama",
                "writer_model": "x",
            },
        )
        assert response.status_code == 400
        assert "missing_vendor" in response.json()["detail"]
    finally:
        client.close()


def test_admin_routing_accepts_enabled_provider(db_session, auth_settings: Settings) -> None:
    client, _admin, settings = _admin_client(db_session, auth_settings)
    try:
        created = client.post(
            "/admin/providers",
            json={
                "name": "groq",
                "display_name": "Groq",
                "base_url": "https://api.groq.com/openai",
                "api_key": "gsk_test_key_9999",
                "enabled": True,
            },
        )
        assert created.status_code == 201, created.text
        response = client.put(
            "/admin/routing",
            json={
                "default_provider": "groq",
                "default_model": "llama-3.1-8b-instant",
                "planner_provider": "groq",
                "planner_model": "llama-3.1-8b-instant",
                "synthesizer_provider": "openai",
                "synthesizer_model": "gpt-4o-mini",
                "reviewer_provider": "groq",
                "reviewer_model": "llama-3.1-8b-instant",
                "writer_provider": "ollama",
                "writer_model": "llama3:8b",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["default_provider"] == "groq"
        assert body["synthesizer_provider"] == "openai"
        assert body["writer_provider"] == "ollama"
    finally:
        client.close()


def test_support_cannot_manage_providers(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(
        update={"auth_disabled": False, "settings_secret_key": "test-settings-secret"},
    )
    support = User(
        id=uuid.uuid4(),
        email="support@example.com",
        display_name="Support",
        role=UserRole.support.value,
        is_active=True,
    )
    db_session.add(support)
    db_session.commit()
    client = build_client(db_session, settings)
    token = create_access_token(user_id=support.id, settings=settings)
    try:
        response = client.get(
            "/admin/providers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        users = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert users.status_code == 200
    finally:
        client.close()
