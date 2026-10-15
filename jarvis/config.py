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

    # Android phone over ADB
    phone_control: bool = True
    adb_path: str = ""          # empty = auto-detect
    adb_serial: str = ""        # empty = first authorised device
    prefer_device: str = "phone"  # "phone" or "laptop" when both can open an app
    multi_task_delay: float = 1.5  # seconds between chained phone actions

    # Voice
    speech_language: str = "en-IN"
    tts_enabled: bool = True
    tts_rate: int = 175
    tts_max_chars: int = 600
    wake_word: bool = True
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.5

    # Web dashboard
    web_host: str = "127.0.0.1"
    web_port: int = 8765

    # Storage
    data_dir: str = str(ROOT_DIR / "data")
    log_dir: str = str(ROOT_DIR / "logs")


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

        if name not in known:
            log.warning("Unknown setting '%s' ignored", name)
            continue

        default = getattr(Settings, name)

        try:
            clean[name] = _coerce(value, type(default))
        except (TypeError, ValueError):
            log.warning("Invalid value for '%s': %r", name, value)

    settings = Settings(**clean)

    if not settings.adb_path:
        settings.adb_path = find_adb() or ""

    return settings
