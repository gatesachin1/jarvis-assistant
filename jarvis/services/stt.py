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
import re
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

# Whisper "hears" these in silence/background noise (artefacts of its training data).
PHANTOM_PHRASES = {
    "you", "thank you", "thanks", "thank you very much", "thanks for watching",
    "thank you for watching", "bye", "okay", "ok", "so", "uh", "um", "hmm", "oh",
    "subtitles by the amara.org community", "please subscribe",
    "jarvis", "hey jarvis", "hi jarvis", "hello jarvis", "ok jarvis", "okay jarvis",
}
# Whisper's own silence rule: a segment is noise only if it looks like non-speech AND
# the decoder was unsure. Requiring just one of these drops real accented speech.
NO_SPEECH_LIMIT = 0.6
LOW_CONFIDENCE = -1.0
GARBAGE_LOGPROB = -2.0  # so unsure it's almost certainly a made-up phrase

# Words JARVIS commands use; priming Whisper with them improves recognition a lot
# ("open YouTube" instead of "open your tool").
VOCABULARY_HINT = (
    "Hey JARVIS. Open YouTube, WhatsApp, Instagram, Spotify, Chrome, Notepad, calculator. "
    "Play music. Remind me to study at 7 pm. Show my reminders. Plan my day. "
    "What time is it? System status. Call mom. Study DBMS normalization. Stop talking."
)
TARGET_PEAK = 0.9  # quiet laptop mics: scale the recording up to this level

_whisper = None
_whisper_lock = threading.Lock()


def _is_noise(seg) -> bool:
    if seg.avg_logprob < GARBAGE_LOGPROB:
        return True
    return seg.no_speech_prob > NO_SPEECH_LIMIT and seg.avg_logprob < LOW_CONFIDENCE


def _sentence_key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


_HINT_SENTENCES = {_sentence_key(s) for s in re.split(r"(?<=[.?])\s+", VOCABULARY_HINT)}


def _echoes_hint(seg) -> bool:
    """A segment that is word-for-word a hint sentence, said with doubt, is the prompt leaking."""

    return _sentence_key(seg.text) in _HINT_SENTENCES and seg.no_speech_prob > 0.3


def clean_transcript(segments) -> str:
    """Join real-speech segments; drop noise, made-up guesses and phantom phrases."""

    kept = [seg.text.strip() for seg in segments if not _is_noise(seg)]
    text = " ".join(t for t in kept if t).strip()
    bare = re.sub(r"[^a-z ]", "", text.lower()).strip()

    if len(bare.replace(" ", "")) < 2 or bare in PHANTOM_PHRASES:
        return ""
    return text


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


def normalize_volume(samples):
    """int16 recording -> float32 in [-1, 1], boosted so quiet speech is at a normal level."""

    import numpy as np

    audio = samples.astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if 0.001 < peak < TARGET_PEAK:
        audio *= min(TARGET_PEAK / peak, 20.0)  # cap the boost so pure hiss isn't blown up
    return audio


def _transcribe_whisper(audio, model: str, models_dir: str, language: str) -> str:
    whisper = load_whisper(model, models_dir)
    audio = normalize_volume(audio)

    # Always keep the speech filter on: without it, Whisper "hears" phrases from the
    # vocabulary hint in pure background noise (e.g. "Play music.").
    segments, _ = whisper.transcribe(
        audio,
        language=language or None,
        beam_size=3,
        condition_on_previous_text=False,
        initial_prompt=VOCABULARY_HINT,
        vad_filter=True,  # skip non-speech audio (fans, music, TV) before decoding
    )
    segments = [seg for seg in segments if not _echoes_hint(seg)]
    log.info(
        "Whisper heard: %s",
        " | ".join(f"{s.text.strip()!r} nsp={s.no_speech_prob:.2f} lp={s.avg_logprob:.2f}" for s in segments)
        or "nothing",
    )

    text = clean_transcript(segments)
    if not text:
        raise JarvisError("I didn't catch that. Please try again, a little closer to the mic.")
    log.info("Voice command: %r", text)
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
