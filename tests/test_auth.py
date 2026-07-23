"""Tests for JWT authentication and dev bypass."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.auth import DEV_USER_ID
from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token
from app.db.session import get_db
from app.main import create_app
from tests.conftest import build_client


def test_create_and_decode_access_token(auth_settings: Settings) -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, settings=auth_settings)
    assert decode_access_token(token, auth_settings) == user_id


def test_auth_me_without_header_when_auth_disabled(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(DEV_USER_ID)
    assert body["email"] == "dev@localhost"


def test_issue_dev_token(client: TestClient) -> None:
    response = client.post("/auth/token", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user_id"] == str(DEV_USER_ID)


def test_auth_me_with_bearer_token_when_auth_enabled(
    db_session,
    auth_settings: Settings,
) -> None:
    from app.db.models import User, UserRole

    auth_settings = auth_settings.model_copy(update={"auth_disabled": False})
    client = build_client(db_session, auth_settings)
    try:
        unauthenticated = client.get("/auth/me")
        assert unauthenticated.status_code == 401

        forbidden = client.post("/auth/token", json={"email": "alice@example.com"})
        assert forbidden.status_code == 403

        user = User(
            id=uuid.uuid4(),
            email="alice@example.com",
            display_name="Alice",
            role=UserRole.user.value,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        token = create_access_token(user_id=user.id, settings=auth_settings)

        authenticated = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert authenticated.status_code == 200
        assert authenticated.json()["email"] == "alice@example.com"
    finally:
        client.close()


def test_invalid_bearer_token_returns_401(db_session, auth_settings: Settings) -> None:
    auth_settings = auth_settings.model_copy(update={"auth_disabled": False})
    client = build_client(db_session, auth_settings)
    try:
        response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert response.status_code == 401
    finally:
        client.close()


def test_token_minting_forbidden_when_auth_enabled(db_session, auth_settings: Settings) -> None:
    auth_settings = auth_settings.model_copy(update={"auth_disabled": False})
    client = build_client(db_session, auth_settings)
    try:
        response = client.post("/auth/token", json={})
        assert response.status_code == 403
    finally:
        client.close()
