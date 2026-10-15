"""A tiny thread-safe publish/subscribe bus shared by the desktop and web UIs.

Event shapes:
    {"type": "message", "sender": "user" | "jarvis", "text": str, "source": str}
    {"type": "status", "state": "idle" | "busy" | "listening", "text": str}
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

log = logging.getLogger(__name__)

Event = dict
Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self, history_size: int = 100):
        self._subscribers: list[Subscriber] = []
        self._lock = threading.Lock()
        self._history: deque[Event] = deque(maxlen=history_size)

    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(subscriber)

        def unsubscribe():
            with self._lock:
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)

        return unsubscribe

    def publish(self, event: Event) -> None:
        event.setdefault("ts", time.time())

        with self._lock:
            if event.get("type") == "message":
                self._history.append(event)
            subscribers = list(self._subscribers)

        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:
                log.exception("Event subscriber failed")

    def history(self) -> list[Event]:
        with self._lock:
            return list(self._history)
