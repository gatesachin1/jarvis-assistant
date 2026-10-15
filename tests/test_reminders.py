import json
from datetime import datetime, timedelta

import pytest

from jarvis.core.errors import JarvisError
from jarvis.services.reminders import ReminderScheduler, ReminderStore, parse_reminder

NOW = datetime(2026, 10, 15, 15, 0)  # 3 pm


@pytest.mark.parametrize(
    "text, task, when",
    [
        ("to call mom at 6 pm", "call mom", NOW.replace(hour=18)),
        ("to call mom at 6:30pm", "call mom", NOW.replace(hour=18, minute=30)),
        ("at 6 to call mom", "call mom", NOW.replace(hour=18)),  # ambiguous -> next 6 o'clock
        ("to drink water in 30 minutes", "drink water", NOW + timedelta(minutes=30)),
        ("to stretch in an hour", "stretch", NOW + timedelta(hours=1)),
        ("to submit DBMS assignment tomorrow at 9 am", "submit DBMS assignment", (NOW + timedelta(days=1)).replace(hour=9)),
        ("to pay fees tomorrow", "pay fees", (NOW + timedelta(days=1)).replace(hour=9)),
        ("to wake up at 7 am", "wake up", (NOW + timedelta(days=1)).replace(hour=7)),  # past -> tomorrow
        ("about the meeting at 14:45", "the meeting", NOW.replace(hour=14, minute=45) + timedelta(days=1)),
    ],
)
def test_parse_reminder(text, task, when):
    assert parse_reminder(text, NOW) == (task, when)


def test_parse_reminder_needs_a_time():
    with pytest.raises(JarvisError):
        parse_reminder("to call mom", NOW)


def test_store_persists_and_migrates_legacy_file(tmp_path):
    legacy = tmp_path / "jarvis_reminders.json"
    legacy.write_text(json.dumps([{"task": "old", "time": "2026-10-16T10:00:00", "done": False}]))

    store = ReminderStore(tmp_path / "data" / "reminders.json", legacy_path=legacy)
    assert [r.task for r in store.pending()] == ["old"]

    store.add("new", datetime(2026, 10, 16, 9, 0))
    reloaded = ReminderStore(tmp_path / "data" / "reminders.json")
    assert [r.task for r in reloaded.pending()] == ["new", "old"]


def test_scheduler_fires_due_reminders_once(tmp_path):
    store = ReminderStore(tmp_path / "r.json")
    store.add("due", NOW - timedelta(minutes=1))
    store.add("later", NOW + timedelta(hours=1))
    fired = []

    scheduler = ReminderScheduler(store, fired.append)
    scheduler.check(NOW)
    scheduler.check(NOW)

    assert [r.task for r in fired] == ["due"]
    assert [r.task for r in store.pending()] == ["later"]
