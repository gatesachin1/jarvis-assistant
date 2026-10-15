"""One-shot speech recognition (Google Web Speech via speech_recognition).

Audio is recorded with sounddevice (the same library the wake word uses), so
PyAudio, which has no prebuilt wheels for newer Pythons, is not needed.
"""

from __future__ import annotations

from collections.abc import Callable

from jarvis.core.errors import JarvisError

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms
CALIBRATE_BLOCKS = 5  # 0.5 s of ambient noise
START_TIMEOUT_BLOCKS = 50  # wait up to 5 s for speech to begin
SILENCE_BLOCKS = 10  # stop after 1 s of silence
MAX_BLOCKS = 120  # 12 s phrase limit


def _record() -> bytes:
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

    return np.concatenate(frames).tobytes()


def listen_once(language: str = "en-IN", on_recognizing: Callable[[], None] = lambda: None) -> str:
    try:
        import speech_recognition as sr
    except ImportError:
        raise JarvisError("Voice input needs the SpeechRecognition package.") from None

    try:
        raw = _record()
    except JarvisError:
        raise
    except ImportError:
        raise JarvisError("Voice input needs the sounddevice package.") from None
    except Exception as error:
        raise JarvisError(f"Microphone not available: {error}") from None

    on_recognizing()

    try:
        return sr.Recognizer().recognize_google(
            sr.AudioData(raw, SAMPLE_RATE, 2), language=language
        )
    except sr.UnknownValueError:
        raise JarvisError("I couldn't understand that.") from None
    except sr.RequestError:
        raise JarvisError("Voice recognition needs an internet connection.") from None
