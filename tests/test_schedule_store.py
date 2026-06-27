from app.services.schedule_store import ScheduleStore


def test_schedule_store_create_and_due(tmp_path):
    store = ScheduleStore(file_path=str(tmp_path / "schedules.json"))
    created = store.create(
        user_id="user-1",
        title="Daily digest",
        prompt="Summarize my documents",
        interval_minutes=60,
    )
    assert created.enabled is True
    assert created.next_run_at

    listed = store.list_for_user("user-1")
    assert len(listed) == 1
    assert listed[0].title == "Daily digest"

    due = store.list_due()
    assert len(due) == 1

    store.mark_run(created.id, run_id="run-123")
    updated = store.get(created.id)
    assert updated is not None
    assert updated.last_run_id == "run-123"
    assert updated.last_run_at

    assert store.delete(user_id="user-1", schedule_id=created.id) is True
    assert store.list_for_user("user-1") == []
