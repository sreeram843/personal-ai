"""Object storage tests."""

from __future__ import annotations

from app.core.config import Settings
from app.services.object_storage import LocalObjectStorage, build_object_storage


def test_local_object_storage_round_trip(tmp_path) -> None:
    storage = LocalObjectStorage(str(tmp_path / "uploads"))
    key = storage.put_bytes(user_id="user-1", filename="notes.txt", payload=b"hello", content_type="text/plain")
    assert key.startswith("user-1/")
    assert "notes.txt" in key
    assert storage.get_uri(key).startswith("file://")


def test_build_object_storage_defaults_to_local() -> None:
    settings = Settings(object_storage_backend="local", object_storage_local_path="memory/uploads")
    storage = build_object_storage(settings)
    assert isinstance(storage, LocalObjectStorage)
