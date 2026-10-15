"""Runtime settings.

Values come from (lowest to highest priority):
    1. the defaults below
    2. config.json in the project root (or the file named by JARVIS_CONFIG)
    3. environment variables named JARVIS_<SETTING>, e.g. JARVIS_OLLAMA_MODEL
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass, fields
from pathlib import Path

# In a PyInstaller build, keep config.json, data/ and logs/ next to JARVIS.exe.
ROOT_DIR = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

log = logging.getLogger(__name__)


@dataclass
class Settings:
    # Local AI (Ollama)
    ollama_model: str = "llama3.2:1b"
    ollama_host: str = "http://127.0.0.1:11434"  # local only; never point this at another machine

    # Android phone over ADB
    phone_control: bool = True
    adb_path: str = ""          # empty = auto-detect
    adb_serial: str = ""        # empty = first authorised device
    prefer_device: str = "phone"  # "phone" or "laptop" when both can open an app
    multi_task_delay: float = 1.5  # seconds between chained phone actions
    adb_wifi_address: str = ""  # e.g. "192.168.1.20:5555"; remembered after "connect phone wirelessly"

    # Voice
    speech_language: str = "en-IN"  # used by the Google engine
    stt_engine: str = "whisper"     # "whisper" (offline) or "google" (online)
    whisper_model: str = "base"     # tiny / base / small - bigger is more accurate but slower
    whisper_language: str = "en"    # "en" keeps Hinglish in Roman script; "" = auto-detect
    tts_engine: str = "piper"       # "piper" (offline neural voice) or "sapi" (Windows voice)
    piper_voice: str = "en_US-lessac-medium"
    tts_enabled: bool = True
    speak_replies: str = "voice"    # "voice" = speak only when you spoke, "always", "never"
    tts_rate: int = 175
    tts_max_chars: int = 300        # long answers: speak the start, show the rest on screen
    wake_word: bool = True
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.5

    # Web dashboard
    web_host: str = "127.0.0.1"
    web_port: int = 8765

    # Storage
    data_dir: str = str(ROOT_DIR / "data")
    log_dir: str = str(ROOT_DIR / "logs")
    models_dir: str = str(ROOT_DIR / "data" / "models")  # Whisper + Piper downloads


def _coerce(value, target_type):
    if isinstance(value, target_type):
        return value

    if target_type is bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    return target_type(value)


def find_adb() -> str | None:
    """Locate adb.exe on PATH, in the Android SDK, or in Downloads."""

    found = shutil.which("adb")
    if found:
        return found

    candidates = []

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
        )

    candidates.append(ROOT_DIR / "platform-tools" / "adb.exe")
    candidates += [
        Path(path)
        for path in glob.glob(
            str(Path.home() / "Downloads" / "platform-tools*" / "**" / "adb.exe"),
            recursive=True,
        )
    ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


CHOICES = {
    "speak_replies": ("voice", "always", "never"),
    "stt_engine": ("whisper", "google"),
    "tts_engine": ("piper", "sapi"),
    "prefer_device": ("phone", "laptop"),
}


def _validate(settings: Settings) -> None:
    """Fall back to the default (with a warning) for typos like "tts_engine": "pipr"."""

    for name, allowed in CHOICES.items():
        value = str(getattr(settings, name)).lower()
        if value not in allowed:
            default = getattr(Settings, name)
            log.warning("Setting %s=%r is not one of %s; using %r", name, value, allowed, default)
            value = default
        setattr(settings, name, value)

    if not 0 < settings.wake_word_threshold < 1:
        log.warning("wake_word_threshold must be between 0 and 1; using 0.5")
        settings.wake_word_threshold = 0.5


def load_settings(path: Path | None = None) -> Settings:
    path = Path(path or os.environ.get("JARVIS_CONFIG") or ROOT_DIR / "config.json")

    values = {}

    if path.exists():
        try:
            values.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as error:
            log.warning("Could not read %s: %s", path, error)

    known = {field.name for field in fields(Settings)}

    for name in known:
        env_value = os.environ.get(f"JARVIS_{name.upper()}")
        if env_value is not None:
            values[name] = env_value

    clean = {}

    for name, value in values.items():
        if name.startswith("_"):
            continue  # allow "_comment" keys in config.json

        if name.endswith("_dir") and not value:
            continue  # empty folder setting = use the default location

        if name not in known:
            log.warning("Unknown setting '%s' ignored", name)
            continue

        default = getattr(Settings, name)

        try:
            clean[name] = _coerce(value, type(default))
        except (TypeError, ValueError):
            log.warning("Invalid value for '%s': %r", name, value)

    settings = Settings(**clean)
    _validate(settings)

    if not settings.adb_path:
        settings.adb_path = find_adb() or ""

    return settings
