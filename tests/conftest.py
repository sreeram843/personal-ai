from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings
from app.core.deps import get_vector_store
from app.db.base import Base
from app.db.session import get_db, get_engine, get_session_factory
from app.main import app as singleton_app, create_app


class _StubVectorStore:
    def search(self, vector, *, user_id: str, limit=4, score_threshold=None):
        return []


@pytest.fixture(autouse=True)
def bind_singleton_app_dependencies(db_session: Session) -> Generator[None, None, None]:
    """Route singleton `app` tests through the in-memory SQLite session."""
    test_settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        dev_user_email="dev@localhost",
        dev_user_display_name="Dev User",
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    singleton_app.dependency_overrides[get_db] = override_get_db
    singleton_app.dependency_overrides[get_settings] = lambda: test_settings
    singleton_app.dependency_overrides[get_vector_store] = lambda: _StubVectorStore()
    yield
    singleton_app.dependency_overrides.clear()
    get_settings.cache_clear()


def apply_db_auth_overrides(app, db_session: Session) -> Settings:
    """Attach in-memory DB + dev auth overrides to a FastAPI app under test."""
    test_settings = Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite://",
        dev_user_email="dev@localhost",
        dev_user_display_name="Dev User",
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    return test_settings


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        auth_disabled=True,
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
        database_url="sqlite:///:memory:",
        dev_user_email="dev@localhost",
        dev_user_display_name="Dev User",
    )


@pytest.fixture
def client(db_session: Session, auth_settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: auth_settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def build_client(db_session: Session, settings: Settings) -> TestClient:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)
