"""Guards against JARVIS talking when it shouldn't (unexpected audio)."""

import json
from types import SimpleNamespace

import pytest

from jarvis.config import load_settings
from jarvis.core.assistant import is_echo
from jarvis.services.stt import clean_transcript


class FakeSpeaker:
    def __init__(self):
        self.spoken = []
        self.stopped = 0
        self.enabled = True
        self.speaking = False

    def say(self, text):
        self.spoken.append(text)

    def stop(self):
        self.stopped += 1

    def set_enabled(self, enabled):
        self.enabled = enabled


@pytest.fixture
def speaker(ctx):
    ctx.speaker = FakeSpeaker()
    return ctx.speaker


def run_sync(assistant, text, source):
    future = assistant.submit(text, source=source)
    if future:
        future.result(timeout=10)


def test_typed_commands_are_not_spoken(assistant, speaker):
    run_sync(assistant, "what time is it", source="text")
    run_sync(assistant, "show my reminders", source="button")
    assert speaker.spoken == []


def test_voice_commands_are_spoken(assistant, speaker):
    run_sync(assistant, "what time is it", source="voice")
    assert len(speaker.spoken) == 1 and speaker.spoken[0].startswith("The time is")


@pytest.mark.parametrize("mode, spoken", [("always", 1), ("never", 0)])
def test_speak_replies_setting(assistant, speaker, ctx, mode, spoken):
    ctx.settings.speak_replies = mode
    run_sync(assistant, "what time is it", source="text")
    assert len(speaker.spoken) == spoken


def test_stop_talking_runs_immediately_even_while_busy(assistant, speaker, ctx):
    import threading

    gate = threading.Event()
    ctx.llm.chat = lambda text: gate.wait(5) and "slow answer"
    assistant.submit("tell me a long story", source="voice")  # occupies the worker

    assert assistant.submit("stop talking", source="voice") is None  # handled inline
    assert speaker.stopped == 1
    gate.set()


def test_own_voice_is_recognised_as_echo():
    said = ["Normalization in DBMS is a process in database design that divides tables."]
    assert is_echo("normalization and DBMS is a process in database design", said)
    assert not is_echo("open youtube on my phone", said)
    assert not is_echo("yes", said)  # too short to judge


def seg(text, no_speech=0.05, logprob=-0.3):
    return SimpleNamespace(text=text, no_speech_prob=no_speech, avg_logprob=logprob)


def test_whisper_noise_and_phantom_phrases_are_dropped():
    assert clean_transcript([seg(" Thank you.")]) == ""
    assert clean_transcript([seg(" you")]) == ""
    assert clean_transcript([seg(" Imagine retrying to predict", no_speech=0.8, logprob=-1.2)]) == ""
    assert clean_transcript([seg(" mumble jumble", logprob=-2.4)]) == ""
    assert clean_transcript([seg(" Open Instagram"), seg(" please")]) == "Open Instagram please"


def test_accented_low_confidence_speech_is_kept():
    # Regression: real speech often has avg_logprob below -1.0; it must not be dropped
    # unless Whisper also thinks it isn't speech.
    assert clean_transcript([seg(" What time is it?", no_speech=0.2, logprob=-1.3)]) == "What time is it?"
    assert clean_transcript([seg(" Open YouTube", no_speech=0.7, logprob=-0.6)]) == "Open YouTube"


def test_quiet_recordings_are_boosted():
    import numpy as np

    from jarvis.services.stt import normalize_volume

    quiet = (np.sin(np.linspace(0, 100, 16000)) * 1500).astype(np.int16)  # ~5% of full scale
    assert 0.85 < float(np.max(np.abs(normalize_volume(quiet)))) <= 0.91
    silence = np.zeros(16000, dtype=np.int16)
    assert float(np.max(np.abs(normalize_volume(silence)))) == 0.0


def test_invalid_settings_fall_back_to_defaults(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"tts_engine": "pipr", "speak_replies": "LOUD", "wake_word_threshold": 3}))
    for var in ("JARVIS_TTS_ENGINE", "JARVIS_SPEAK_REPLIES", "JARVIS_WAKE_WORD_THRESHOLD"):
        monkeypatch.delenv(var, raising=False)

    settings = load_settings(config)
    assert (settings.tts_engine, settings.speak_replies, settings.wake_word_threshold) == ("piper", "voice", 0.5)
