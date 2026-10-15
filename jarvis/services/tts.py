"""Text-to-speech on one dedicated thread.

Engines:
    piper  offline neural voice (default), played with sounddevice.
    sapi   the built-in Windows voice via pyttsx3 (fallback).

pyttsx3 hangs on Windows when runAndWait() is called from a new thread each
time (v1 did this), so a single worker owns the engine and reads from a queue.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)


def clean_for_speech(text: str, max_chars: int) -> str:
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"[*#`_>|•⏰]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_chars:
        cut = text.rfind(". ", 0, max_chars)
        text = text[: cut + 1 if cut > 0 else max_chars] + " The full answer is on screen."
    return text


class _SapiEngine:
    def __init__(self, rate: int):
        try:
            import comtypes  # SAPI5 needs COM initialised on this thread

            comtypes.CoInitialize()
        except Exception:
            pass

        import pyttsx3

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

    def speak(self, text: str) -> None:
        self.engine.say(text)
        self.engine.runAndWait()

    def stop(self) -> None:
        self.engine.stop()


class _PiperEngine:
    def __init__(self, voice: str, models_dir: str, rate: int):
        from piper import PiperVoice, SynthesisConfig
        from piper.download_voices import download_voice

        folder = Path(models_dir) / "piper"
        folder.mkdir(parents=True, exist_ok=True)
        model = folder / f"{voice}.onnx"

        if not model.exists():
            log.info("Downloading Piper voice %s...", voice)
            download_voice(voice, folder)

        self.voice = PiperVoice.load(model)
        # pyttsx3 rate 175 ~ normal speed; Piper uses length_scale (lower = faster).
        self.config = SynthesisConfig(length_scale=max(0.6, min(1.5, 175 / max(rate, 50))))
        self._stopped = threading.Event()

    def speak(self, text: str) -> None:
        import sounddevice as sd

        self._stopped.clear()
        for chunk in self.voice.synthesize(text, syn_config=self.config):
            if self._stopped.is_set():
                return
            sd.play(chunk.audio_float_array, chunk.sample_rate)
            sd.wait()

    def stop(self) -> None:
        import sounddevice as sd

        self._stopped.set()
        sd.stop()


class Speaker:
    def __init__(
        self,
        rate: int = 175,
        enabled: bool = True,
        max_chars: int = 600,
        engine: str = "sapi",
        piper_voice: str = "en_US-lessac-medium",
        models_dir: str = "models",
    ):
        self.rate = rate
        self.enabled = enabled
        self.max_chars = max_chars
        self.engine_name = engine
        self.piper_voice = piper_voice
        self.models_dir = models_dir
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._engine = None
        self._busy = False
        self._finished_at = 0.0

    @property
    def speaking(self) -> bool:
        """True while talking and for a moment after (so the mic doesn't catch the echo)."""

        return self._busy or not self._queue.empty() or time.monotonic() - self._finished_at < 0.8

    def start(self) -> None:
        """Start the worker early so the voice model loads before the first reply."""

        if self._thread is None:
            self._thread = threading.Thread(target=self._worker, name="jarvis-tts", daemon=True)
            self._thread.start()

    def say(self, text: str) -> None:
        if not self.enabled or not text:
            return
        self.start()
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

    def _load_engine(self):
        if self.engine_name == "piper":
            try:
                engine = _PiperEngine(self.piper_voice, self.models_dir, self.rate)
                log.info("Using Piper voice %s", self.piper_voice)
                return engine
            except Exception:
                log.exception("Piper voice unavailable; using the Windows voice")
        return _SapiEngine(self.rate)

    def _worker(self) -> None:
        try:
            self._engine = self._load_engine()
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
            self._busy = True
            try:
                self._engine.speak(text)
            except Exception:
                log.exception("Speech failed")
            finally:
                self._busy = False
                self._finished_at = time.monotonic()
