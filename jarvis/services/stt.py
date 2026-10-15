"""One-shot speech recognition.

Engines:
    whisper  offline, via faster-whisper (default). Better with Indian accents
             and Hinglish, and works without internet.
    google   Google Web Speech via speech_recognition (needs internet).

Audio is recorded with sounddevice (the same library the wake word uses), so
PyAudio, which has no prebuilt wheels for newer Pythons, is not needed.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable

from jarvis.core.errors import JarvisError

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms
CALIBRATE_BLOCKS = 5  # 0.5 s of ambient noise
START_TIMEOUT_BLOCKS = 50  # wait up to 5 s for speech to begin
SILENCE_BLOCKS = 10  # stop after 1 s of silence
MAX_BLOCKS = 120  # 12 s phrase limit

_whisper = None
_whisper_lock = threading.Lock()


def _record():
    import numpy as np
    import sounddevice as sd

    def energy(block):
        return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK) as stream:
        ambient = [energy(stream.read(BLOCK)[0]) for _ in range(CALIBRATE_BLOCKS)]
        threshold = max(300.0, sum(ambient) / len(ambient) * 2.5)

        # Wait for speech to start (keep a little lead-in so the first word isn't clipped).
        lead_in = []
        for _ in range(START_TIMEOUT_BLOCKS):
            block = stream.read(BLOCK)[0]
            if energy(block) > threshold:
                frames = lead_in[-3:] + [block]
                break
            lead_in.append(block)
        else:
            raise JarvisError("No speech detected.")

        silent = 0
        while len(frames) < MAX_BLOCKS and silent < SILENCE_BLOCKS:
            block = stream.read(BLOCK)[0]
            frames.append(block)
            silent = silent + 1 if energy(block) < threshold else 0

    return np.concatenate(frames).flatten()


# ------------------------------------------------------------------ whisper

def load_whisper(model: str, models_dir: str):
    """Load (downloading on first use) the Whisper model. Safe to call from a warm-up thread."""

    global _whisper
    with _whisper_lock:
        if _whisper is None:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
            os.environ.setdefault("HF_HUB_VERBOSITY", "error")
            from faster_whisper import WhisperModel

            log.info("Loading Whisper '%s' model (first run downloads it)...", model)
            _whisper = WhisperModel(model, device="cpu", compute_type="int8", download_root=models_dir)
            log.info("Whisper ready")
        return _whisper


def _transcribe_whisper(audio, model: str, models_dir: str, language: str) -> str:
    import numpy as np

    whisper = load_whisper(model, models_dir)
    segments, _ = whisper.transcribe(
        audio.astype(np.float32) / 32768.0,
        language=language or None,
        beam_size=1,
        condition_on_previous_text=False,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise JarvisError("I couldn't understand that.")
    return text


def _transcribe_google(audio, language: str) -> str:
    try:
        import speech_recognition as sr
    except ImportError:
        raise JarvisError("Voice input needs the SpeechRecognition package.") from None

    try:
        return sr.Recognizer().recognize_google(
            sr.AudioData(audio.tobytes(), SAMPLE_RATE, 2), language=language
        )
    except sr.UnknownValueError:
        raise JarvisError("I couldn't understand that.") from None
    except sr.RequestError:
        raise JarvisError("Voice recognition needs an internet connection.") from None


# --------------------------------------------------------------------- API

def listen_once(settings, on_recognizing: Callable[[], None] = lambda: None) -> str:
    try:
        audio = _record()
    except JarvisError:
        raise
    except ImportError:
        raise JarvisError("Voice input needs the sounddevice package.") from None
    except Exception as error:
        raise JarvisError(f"Microphone not available: {error}") from None

    on_recognizing()

    if settings.stt_engine == "whisper":
        try:
            return _transcribe_whisper(
                audio, settings.whisper_model, settings.models_dir, settings.whisper_language
            )
        except JarvisError:
            raise
        except Exception:
            log.exception("Whisper failed; falling back to Google")

    return _transcribe_google(audio, settings.speech_language)
