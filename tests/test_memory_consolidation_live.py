"""Live wiring for per-user MemoryConsolidationService."""

from datetime import datetime, timedelta

from app.core.config import get_settings
from app.schemas.memory import MemoryEntry, MemoryTier
from app.services.chat_execution import record_post_chat_memory
from app.services.memory_consolidation import MemoryConsolidationService
from app.services.prompt_context import augment_system_prompt
from app.services.user_memory import UserMemoryStore


def test_persistence_round_trip(tmp_path):
    path = str(tmp_path / "consolidation.json")
    service = MemoryConsolidationService(file_path=path)
    entry = MemoryEntry(
        id="e1",
        tier=MemoryTier.DURABLE,
        content="prefers dark mode",
        confidence=0.9,
    )
    service.add_entry_for_user(entry, "user-a")

    reloaded = MemoryConsolidationService(file_path=path)
    retrieved = reloaded.retrieve_relevant("user-a")
    assert len(retrieved) == 1
    assert retrieved[0].id == "e1"
    assert retrieved[0].content == "prefers dark mode"
    assert retrieved[0].tier == MemoryTier.DURABLE


def test_tenant_isolation(tmp_path):
    service = MemoryConsolidationService(file_path=str(tmp_path / "consolidation.json"))
    service.add_entry_for_user(
        MemoryEntry(id="a", tier=MemoryTier.DURABLE, content="user a secret", confidence=0.9),
        "user-a",
    )
    service.add_entry_for_user(
        MemoryEntry(id="b", tier=MemoryTier.DURABLE, content="user b secret", confidence=0.9),
        "user-b",
    )

    a_hits = service.retrieve_relevant("user-a")
    b_hits = service.retrieve_relevant("user-b")
    assert [entry.content for entry in a_hits] == ["user a secret"]
    assert [entry.content for entry in b_hits] == ["user b secret"]


def test_stale_and_low_confidence_drop_from_memory_block(tmp_path):
    store = UserMemoryStore(file_path=str(tmp_path / "user_memory.json"))
    consolidation = MemoryConsolidationService(file_path=str(tmp_path / "consolidation.json"))

    consolidation.add_entry_for_user(
        MemoryEntry(
            id="good",
            tier=MemoryTier.DURABLE,
            content="likes espresso",
            confidence=0.9,
            freshness=1.0,
        ),
        "user-1",
    )
    consolidation.add_entry_for_user(
        MemoryEntry(
            id="low",
            tier=MemoryTier.DURABLE,
            content="maybe likes tea",
            confidence=0.1,
            freshness=1.0,
        ),
        "user-1",
    )
    stale_freshness = MemoryEntry(
        id="stale-freshness",
        tier=MemoryTier.EPHEMERAL,
        content="old session note",
        confidence=0.9,
        freshness=0.1,
    )
    stale_freshness.created_at = datetime.utcnow() - timedelta(days=14)
    consolidation.add_entry_for_user(stale_freshness, "user-1")
    ttl_stale = MemoryEntry(
        id="ttl",
        tier=MemoryTier.EPHEMERAL,
        content="expired ttl fact",
        confidence=0.9,
        ttl_hours=1,
    )
    ttl_stale.created_at = datetime.utcnow() - timedelta(hours=2)
    consolidation.add_entry_for_user(ttl_stale, "user-1")

    block = store.get_memory_block("user-1", consolidation_service=consolidation)
    assert "likes espresso" in block
    assert "confidence 0.90" in block
    assert "maybe likes tea" not in block
    assert "old session note" not in block
    assert "expired ttl fact" not in block

    job = consolidation.schedule_consolidation("user-1")
    assert consolidation.run_consolidation(job.job_id)
    remaining_ids = {entry.id for entry in consolidation.retrieve_relevant("user-1", limit=20)}
    assert "ttl" not in remaining_ids
    assert "stale-freshness" not in remaining_ids
    assert "good" in remaining_ids

    block_after = store.get_memory_block("user-1", consolidation_service=consolidation)
    assert "likes espresso" in block_after
    assert "expired ttl fact" not in block_after
    assert "old session note" not in block_after


def test_record_turn_then_memory_block(tmp_path):
    store = UserMemoryStore(file_path=str(tmp_path / "user_memory.json"))
    consolidation = MemoryConsolidationService(file_path=str(tmp_path / "consolidation.json"))
    consolidation.record_turn(
        "user-1",
        user_message="Remember that I commute by bike",
        assistant_message="Noted — I'll keep that in mind.",
    )
    block = store.get_memory_block("user-1", consolidation_service=consolidation)
    assert "commute by bike" in block
    assert "confidence" in block


def test_record_post_chat_memory_ingests_consolidation(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_MEMORY_CONSOLIDATION", "true")
    monkeypatch.setenv("ENABLE_USER_MEMORY", "true")
    monkeypatch.setenv("USER_MEMORY_PATH", str(tmp_path / "user_memory.json"))
    monkeypatch.setenv("MEMORY_CONSOLIDATION_PATH", str(tmp_path / "consolidation.json"))
    get_settings.cache_clear()
    from app.core import deps

    deps.get_user_memory_store.cache_clear()
    deps.get_memory_consolidation_service.cache_clear()

    record_post_chat_memory(
        user_id="u1",
        user_message="I prefer dark mode",
        assistant_message="Got it.",
    )
    service = deps.get_memory_consolidation_service()
    hits = service.retrieve_relevant("u1")
    assert hits
    assert "dark mode" in hits[0].content

    store = deps.get_user_memory_store()
    block = store.get_memory_block("u1", consolidation_service=service)
    assert "dark mode" in block

    deps.get_user_memory_store.cache_clear()
    deps.get_memory_consolidation_service.cache_clear()
    get_settings.cache_clear()


def test_prompt_context_includes_consolidation_facts(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_MEMORY_CONSOLIDATION", "true")
    monkeypatch.setenv("ENABLE_USER_MEMORY", "true")
    monkeypatch.setenv("MEMORY_CONSOLIDATION_PATH", str(tmp_path / "consolidation.json"))
    get_settings.cache_clear()
    from app.core import deps

    deps.get_memory_consolidation_service.cache_clear()
    service = deps.get_memory_consolidation_service()
    service.add_entry_for_user(
        MemoryEntry(
            id="pref",
            tier=MemoryTier.DURABLE,
            content="timezone is Pacific",
            confidence=0.85,
            freshness=1.0,
        ),
        "u-prompt",
    )
    store = UserMemoryStore(file_path=str(tmp_path / "user_memory.json"))
    settings = get_settings()
    prompt = augment_system_prompt(
        "Base prompt",
        user_query="hello",
        user_id="u-prompt",
        settings=settings,
        user_memory_store=store,
    )
    assert "timezone is Pacific" in prompt
    deps.get_memory_consolidation_service.cache_clear()
    get_settings.cache_clear()
