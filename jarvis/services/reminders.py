"""Reminder storage, natural-language time parsing and the background scheduler."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from jarvis.core.errors import JarvisError

log = logging.getLogger(__name__)


@dataclass
class Reminder:
    id: str
    task: str
    time: str  # ISO format
    done: bool = False

    @property
    def when(self) -> datetime:
        return datetime.fromisoformat(self.time)


class ReminderStore:
    def __init__(self, path: Path, legacy_path: Path | None = None):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._items: list[Reminder] = self._load(legacy_path)

    # --------------------------------------------------------------- storage

    def _load(self, legacy_path: Path | None) -> list[Reminder]:
        source = self.path
        if not source.exists() and legacy_path and Path(legacy_path).exists():
            source = Path(legacy_path)
            log.info("Migrating reminders from %s", source)

        if not source.exists():
            return []

        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.exception("Reminder file is unreadable; starting empty")
            return []

        items = []
        for entry in raw:
            try:
                items.append(
                    Reminder(
                        id=entry.get("id") or uuid.uuid4().hex[:8],
                        task=str(entry["task"]),
                        time=datetime.fromisoformat(entry["time"]).isoformat(),
                        done=bool(entry.get("done", False)),
                    )
                )
            except (KeyError, ValueError, TypeError):
                log.warning("Skipping invalid reminder: %r", entry)

        if source != self.path:
            self._items = items
            self._save()
        return items

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps([asdict(item) for item in self._items], indent=2)

        # Write to a temp file then rename, so a crash never leaves half a file.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(data)
        os.replace(tmp, self.path)

    # ----------------------------------------------------------------- API

    def add(self, task: str, when: datetime) -> Reminder:
        with self._lock:
            reminder = Reminder(id=uuid.uuid4().hex[:8], task=task, time=when.isoformat())
            self._items.append(reminder)
            self._save()
            return reminder

    def pending(self) -> list[Reminder]:
        with self._lock:
            return sorted((r for r in self._items if not r.done), key=lambda r: r.when)

    def due(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now()
        return [r for r in self.pending() if r.when <= now]

    def complete(self, reminder_id: str) -> Reminder | None:
        with self._lock:
            for reminder in self._items:
                if reminder.id == reminder_id:
                    reminder.done = True
                    self._save()
                    return reminder
        return None

    def delete(self, reminder_id: str) -> Reminder | None:
        with self._lock:
            for reminder in self._items:
                if reminder.id == reminder_id:
                    self._items.remove(reminder)
                    self._save()
                    return reminder
        return None

    def clear_pending(self) -> int:
        with self._lock:
            before = len(self._items)
            self._items = [r for r in self._items if r.done]
            self._save()
            return before - len(self._items)

    def by_number(self, number: int) -> Reminder:
        """Look up the Nth reminder as shown by 'show reminders' (1-based)."""

        pending = self.pending()
        if not 1 <= number <= len(pending):
            raise JarvisError(f"There is no reminder number {number}.")
        return pending[number - 1]


# ------------------------------------------------------------------ parsing

_RELATIVE = re.compile(
    r"\b(?:in|after)\s+(\d+|an?|one)\s*(minutes?|mins?|hours?|hrs?)\b", re.I
)
_DAY = re.compile(r"\b(today|tonight|tomorrow|kal)\b", re.I)
_CLOCK = re.compile(
    r"\b(?:at\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?!\w)"
    r"|\bat\s+(\d{1,2})(?:[:.](\d{2}))?\b",
    re.I,
)
_NAMED = {"noon": (12, 0), "midnight": (0, 0), "morning": (9, 0), "evening": (18, 0)}
_NAMED_RE = re.compile(r"\b(?:at\s+|in the\s+|this\s+)?(noon|midnight|morning|evening)\b", re.I)


def parse_reminder(text: str, now: datetime | None = None) -> tuple[str, datetime]:
    """'to call mom at 6 pm' -> ('call mom', <today 18:00>)."""

    now = (now or datetime.now()).replace(second=0, microsecond=0)
    rest = f" {text.strip()} "
    when = None

    relative = _RELATIVE.search(rest)
    if relative:
        amount = 1 if relative.group(1).lower() in {"a", "an", "one"} else int(relative.group(1))
        unit = relative.group(2).lower()
        when = now + (timedelta(hours=amount) if unit.startswith("h") else timedelta(minutes=amount))
        rest = rest.replace(relative.group(0), " ")

    day_offset = None
    day = _DAY.search(rest)
    if day:
        day_offset = 1 if day.group(1).lower() in {"tomorrow", "kal"} else 0
        rest = rest.replace(day.group(0), " ")

    hour = minute = None
    clock = _CLOCK.search(rest)
    if clock and not when:
        if clock.group(1):
            hour, minute, meridiem = int(clock.group(1)), int(clock.group(2) or 0), clock.group(3)
            meridiem = meridiem.lower().replace(".", "")
            if not 1 <= hour <= 12:
                raise JarvisError("That time doesn't look right.")
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
        else:
            hour, minute = int(clock.group(4)), int(clock.group(5) or 0)
            if hour > 23:
                raise JarvisError("That time doesn't look right.")
            if hour <= 12 and day and day.group(1).lower() == "tonight" and hour < 12:
                hour += 12
        rest = rest.replace(clock.group(0), " ")
    elif not when:
        named = _NAMED_RE.search(rest)
        if named:
            hour, minute = _NAMED[named.group(1).lower()]
            rest = rest.replace(named.group(0), " ")

    if minute is not None and minute > 59:
        raise JarvisError("That time doesn't look right.")

    if not when:
        if hour is None and day_offset is None:
            raise JarvisError(
                "When should I remind you? Try 'remind me to call mom at 6 pm' "
                "or 'remind me to drink water in 30 minutes'."
            )

        if hour is None:
            hour, minute = (9, 0) if day_offset else (now.hour + 1, 0)

        base = now + timedelta(days=day_offset or 0)
        when = base.replace(hour=hour % 24, minute=minute)

        ambiguous = clock is not None and clock.group(4) and hour < 12
        if day_offset is None and when <= now:
            # "at 6" said at 3 pm means 6 pm, otherwise roll over to tomorrow.
            if ambiguous and when + timedelta(hours=12) > now:
                when += timedelta(hours=12)
            else:
                when += timedelta(days=1)

    task = re.sub(r"\s+", " ", rest).strip(" ,.")
    task = re.sub(r"^(?:to|that|about|for)\s+", "", task, flags=re.I)
    task = re.sub(r"\s+(?:to|that|about|for)$", "", task, flags=re.I).strip()

    if not task:
        raise JarvisError("What should I remind you about?")

    return task, when


def format_when(when: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    clock = when.strftime("%I:%M %p").lstrip("0")

    if when.date() == now.date():
        return f"today at {clock}"
    if when.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {clock}"
    return when.strftime("%d %b at ") + clock


# ---------------------------------------------------------------- scheduler

class ReminderScheduler:
    """Checks for due reminders every few seconds and announces them."""

    def __init__(self, store: ReminderStore, on_due: Callable[[Reminder], None], interval: float = 15):
        self.store = store
        self.on_due = on_due
        self.interval = interval
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._loop, name="jarvis-reminders", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def check(self, now: datetime | None = None) -> list[Reminder]:
        fired = []
        for reminder in self.store.due(now):
            self.store.complete(reminder.id)
            fired.append(reminder)
            try:
                self.on_due(reminder)
            except Exception:
                log.exception("Reminder callback failed")
        return fired

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.check()
            self._stop.wait(self.interval)
