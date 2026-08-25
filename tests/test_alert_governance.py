from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.config import Settings, get_settings
from app.services.alert_governance import (
    AlertGovernance,
    build_alert_governance,
    condition_key,
    schedule_tier,
)
from app.services.schedule_store import ScheduleStore, ScheduledReport
from app.workers.tasks import scheduled_reports_tick

NOW = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)


def _gov(tmp_path, *, minutes: int = 60) -> AlertGovernance:
    return AlertGovernance(
        file_path=str(tmp_path / "alert_governance.json"),
        refractory_minutes=minutes,
    )


def test_same_condition_suppressed_within_window(tmp_path):
    gov = _gov(tmp_path)
    key = condition_key(user_id="user-1", schedule_id="sched-1", prompt="Daily digest")
    assert gov.should_notify(key, tier="actionable", now=NOW) is True
    gov.record_fire(key, tier="actionable", now=NOW)

    assert gov.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=1)) is False
    assert gov.suppressed == 1
    assert gov.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=59)) is False
    assert gov.suppressed == 2


def test_same_condition_notifies_after_window(tmp_path):
    gov = _gov(tmp_path)
    key = condition_key(user_id="user-1", schedule_id="sched-1", prompt="Daily digest")
    gov.record_fire(key, tier="actionable", now=NOW)
    assert gov.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=60)) is True
    assert gov.suppressed == 0


def test_window_is_configurable(tmp_path, monkeypatch):
    short = _gov(tmp_path, minutes=10)
    key = condition_key(user_id="user-1", schedule_id="sched-1", prompt="prompt")
    short.record_fire(key, tier="actionable", now=NOW)
    assert short.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=9)) is False
    assert short.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=10)) is True

    monkeypatch.setenv("ALERT_GOVERNANCE_PATH", str(tmp_path / "from-settings.json"))
    monkeypatch.setenv("ALERT_REFRACTORY_MINUTES", "5")
    get_settings.cache_clear()
    from_settings = build_alert_governance()
    assert from_settings.refractory_minutes == 5
    from_settings.record_fire(key, tier="actionable", now=NOW)
    assert from_settings.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=4)) is False
    assert from_settings.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=5)) is True
    get_settings.cache_clear()


def test_different_schedule_ids_are_independent(tmp_path):
    gov = _gov(tmp_path)
    key_a = condition_key(user_id="user-1", schedule_id="sched-a", prompt="same prompt")
    key_b = condition_key(user_id="user-1", schedule_id="sched-b", prompt="same prompt")
    assert key_a != key_b
    gov.record_fire(key_a, tier="actionable", now=NOW)
    assert gov.should_notify(key_b, tier="actionable", now=NOW + timedelta(minutes=1)) is True
    assert gov.suppressed == 0


def test_informational_uses_double_window_and_skips_repeats(tmp_path):
    gov = _gov(tmp_path, minutes=60)
    key = condition_key(user_id="user-1", schedule_id="sched-1", prompt="FYI")
    gov.record_fire(key, tier="informational", now=NOW)
    # Informational repeat: still inside 2x window at 60 minutes.
    assert gov.should_notify(key, tier="informational", now=NOW + timedelta(minutes=60)) is False
    assert gov.suppressed == 1
    assert gov.should_notify(key, tier="informational", now=NOW + timedelta(minutes=120)) is True
    # Escalation to actionable is allowed inside the informational window.
    assert gov.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=10)) is True


def test_schedule_tier_defaults_actionable_and_reads_metadata():
    default = ScheduledReport(
        id="s1",
        user_id="u1",
        title="Digest",
        prompt="Summarize",
        interval_minutes=15,
    )
    assert schedule_tier(default) == "actionable"
    informational = ScheduledReport(
        id="s2",
        user_id="u1",
        title="FYI",
        prompt="Ping",
        interval_minutes=15,
        metadata={"tier": "informational"},
    )
    assert schedule_tier(informational) == "informational"
    from_payload = SimpleNamespace(metadata=None, payload={"tier": "informational"}, tier=None)
    assert schedule_tier(from_payload) == "informational"


def test_record_fire_persists_last_fired_at_and_tier(tmp_path):
    path = tmp_path / "alert_governance.json"
    gov = AlertGovernance(file_path=str(path), refractory_minutes=60)
    key = condition_key(user_id="user-1", schedule_id="sched-1", prompt="x")
    gov.record_fire(key, tier="actionable", now=NOW)
    reloaded = AlertGovernance(file_path=str(path), refractory_minutes=60)
    assert reloaded.should_notify(key, tier="actionable", now=NOW + timedelta(minutes=1)) is False


class _StubQueue:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def enqueue_workflow(self, **kwargs):
        self.calls.append(kwargs)


class _StubRunStore:
    def create_run(self, **kwargs):
        return SimpleNamespace(run_id="run-1")


def test_tick_skips_enqueue_when_should_notify_false(tmp_path, monkeypatch):
    gov_path = tmp_path / "alert_governance.json"
    settings = Settings(
        enable_background_workers=True,
        alert_governance_path=str(gov_path),
        alert_refractory_minutes=60,
    )
    monkeypatch.setattr("app.workers.tasks.get_settings", lambda: settings)

    schedule = ScheduledReport(
        id="sched-1",
        user_id="user-1",
        title="Daily",
        prompt="Summarize my documents",
        interval_minutes=15,
    )
    prior = AlertGovernance(file_path=str(gov_path), refractory_minutes=60)
    prior.record_fire(
        condition_key(user_id=schedule.user_id, schedule_id=schedule.id, prompt=schedule.prompt),
        tier="actionable",
        now=datetime.now(timezone.utc),
    )

    class StubStore:
        def __init__(self) -> None:
            self.mark_calls: list[tuple[str, str]] = []

        def list_due(self):
            return [schedule]

        def mark_run(self, schedule_id: str, *, run_id: str) -> None:
            self.mark_calls.append((schedule_id, run_id))

    store = StubStore()
    queue = _StubQueue()
    monkeypatch.setattr("app.core.deps.get_schedule_store", lambda: store)
    monkeypatch.setattr("app.core.deps.get_run_store", lambda: _StubRunStore())
    monkeypatch.setattr("app.services.task_queue.get_task_queue", lambda: queue)

    result = asyncio.run(scheduled_reports_tick({}))
    assert queue.calls == []
    assert store.mark_calls == [("sched-1", "suppressed")]
    assert result["processed"] == 1
    assert result["suppressed"] == 1


def test_tick_mark_run_clears_due_when_suppressed(tmp_path, monkeypatch):
    store = ScheduleStore(file_path=str(tmp_path / "schedules.json"))
    created = store.create(
        user_id="user-1",
        title="Daily digest",
        prompt="Summarize my documents",
        interval_minutes=15,
    )
    assert len(store.list_due()) == 1

    settings = Settings(
        enable_background_workers=True,
        alert_governance_path=str(tmp_path / "alert_governance.json"),
        alert_refractory_minutes=60,
    )
    monkeypatch.setattr("app.workers.tasks.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.deps.get_schedule_store", lambda: store)
    monkeypatch.setattr("app.core.deps.get_run_store", lambda: _StubRunStore())
    queue = _StubQueue()
    monkeypatch.setattr("app.services.task_queue.get_task_queue", lambda: queue)
    prior = AlertGovernance(
        file_path=str(tmp_path / "alert_governance.json"),
        refractory_minutes=60,
    )
    prior.record_fire(
        condition_key(user_id=created.user_id, schedule_id=created.id, prompt=created.prompt),
        tier="actionable",
        now=datetime.now(timezone.utc),
    )

    result = asyncio.run(scheduled_reports_tick({}))
    assert queue.calls == []
    assert result["suppressed"] == 1
    updated = store.get(created.id)
    assert updated is not None
    assert updated.last_run_id == "suppressed"
    assert store.list_due() == []


def test_tick_enqueues_when_governance_allows(tmp_path, monkeypatch):
    settings = Settings(
        enable_background_workers=True,
        alert_governance_path=str(tmp_path / "alert_governance.json"),
        alert_refractory_minutes=60,
    )
    monkeypatch.setattr("app.workers.tasks.get_settings", lambda: settings)

    schedule = ScheduledReport(
        id="sched-1",
        user_id="user-1",
        title="Daily",
        prompt="Summarize my documents",
        interval_minutes=15,
    )

    class StubStore:
        def __init__(self) -> None:
            self.mark_calls: list[tuple[str, str]] = []

        def list_due(self):
            return [schedule]

        def mark_run(self, schedule_id: str, *, run_id: str) -> None:
            self.mark_calls.append((schedule_id, run_id))

    store = StubStore()
    queue = _StubQueue()
    monkeypatch.setattr("app.core.deps.get_schedule_store", lambda: store)
    monkeypatch.setattr("app.core.deps.get_run_store", lambda: _StubRunStore())
    monkeypatch.setattr("app.services.task_queue.get_task_queue", lambda: queue)

    result = asyncio.run(scheduled_reports_tick({}))
    assert len(queue.calls) == 1
    assert queue.calls[0]["run_id"] == "run-1"
    assert store.mark_calls == [("sched-1", "run-1")]
    assert result["processed"] == 1
    assert result["suppressed"] == 0
