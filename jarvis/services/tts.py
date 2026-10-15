"""Text-to-speech on one dedicated thread.

pyttsx3 hangs on Windows when runAndWait() is called from a new thread each
time (v1 did this), so a single worker owns the engine and reads from a queue.
"""

from __future__ import annotations

import logging
import queue
import re
import threading

log = logging.getLogger(__name__)


def clean_for_speech(text: str, max_chars: int) -> str:
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"[*#`_>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_chars:
        cut = text.rfind(". ", 0, max_chars)
        text = text[: cut + 1 if cut > 0 else max_chars] + " The full answer is on screen."
    return text


class Speaker:
    def __init__(self, rate: int = 175, enabled: bool = True, max_chars: int = 600):
        self.rate = rate
        self.enabled = enabled
        self.max_chars = max_chars
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._engine = None

    def say(self, text: str) -> None:
        if not self.enabled or not text:
            return

        if self._thread is None:
            self._thread = threading.Thread(target=self._worker, name="jarvis-tts", daemon=True)
            self._thread.start()

        self._queue.put(clean_for_speech(text, self.max_chars))

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.stop()

    def stop(self) -> None:
        """Drop queued speech and interrupt the current sentence."""

        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def _worker(self) -> None:
        try:
            try:
                import comtypes  # SAPI5 needs COM initialised on this thread

                comtypes.CoInitialize()
            except Exception:
                pass

            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
        except Exception:
            log.exception("Text-to-speech is unavailable")
            self.enabled = False
            return

        while True:
            text = self._queue.get()
            if text is None:
                return
            if not self.enabled:
                continue
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                log.exception("Speech failed")
