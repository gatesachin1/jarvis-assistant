"""'Hey JARVIS' wake word detection with openWakeWord.

v1 called sd.rec() for every 80 ms chunk, which leaves gaps between chunks
(missed words) and restarted itself recursively on errors. This version reads
one continuous InputStream, pauses while a command is being recorded, and
backs off on errors.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK = 1280  # 80 ms, what openWakeWord expects
COOLDOWN_SECONDS = 2.0
PATIENCE_FRAMES = 2  # a real "Hey JARVIS" scores high on several frames; a click or cough on one


class WakeWordListener:
    def __init__(
        self,
        model_name: str,
        threshold: float,
        on_wake: Callable[[], None],
        on_status: Callable[[str], None] = lambda _: None,
        is_suppressed: Callable[[], bool] = lambda: False,
    ):
        self.model_name = model_name
        self.threshold = threshold
        self.on_wake = on_wake
        self.on_status = on_status
        self.is_suppressed = is_suppressed  # e.g. JARVIS is speaking: don't wake on our own voice
        self._active = threading.Event()
        self._active.set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="jarvis-wakeword", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._active.set()

    def pause(self) -> None:
        self._active.clear()

    def resume(self) -> None:
        self._active.set()

    @property
    def paused(self) -> bool:
        return not self._active.is_set()

    def _load_model(self):
        import openwakeword
        from openwakeword.model import Model

        try:
            openwakeword.utils.download_models(model_names=[self.model_name])
        except Exception:
            log.warning("Could not download wake word model; using cached copy if present")

        return Model(wakeword_models=[self.model_name], inference_framework="onnx")

    def _run(self) -> None:
        try:
            import sounddevice as sd

            model = self._load_model()
        except Exception as error:
            log.exception("Wake word unavailable")
            self.on_status(f"Wake word unavailable: {error}")
            return

        backoff = 2
        self.on_status("Say 'Hey JARVIS'")

        while not self._stop.is_set():
            self._active.wait()
            if self._stop.is_set():
                return

            try:
                with sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK
                ) as stream:
                    backoff = 2
                    hits = 0
                    while self._active.is_set() and not self._stop.is_set():
                        audio, _ = stream.read(CHUNK)
                        if self.is_suppressed():
                            model.reset()
                            hits = 0
                            continue
                        scores = model.predict(audio.flatten())
                        hits = hits + 1 if max(scores.values(), default=0) >= self.threshold else 0

                        if hits >= PATIENCE_FRAMES:
                            log.info("Wake word detected %s", scores)
                            model.reset()
                            self.pause()  # release the mic for the command
                            self.on_wake()
                            break

                time.sleep(COOLDOWN_SECONDS if self._active.is_set() else 0)

            except Exception as error:
                log.warning("Wake word stream error: %s (retrying in %ss)", error, backoff)
                self.on_status("Wake word listener error, retrying...")
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 60)
