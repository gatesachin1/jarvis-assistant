"""Everything a skill handler needs, injected so skills can be unit-tested with fakes."""

from __future__ import annotations

import subprocess
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis.config import Settings


def launch_process(argv: list[str], new_console: bool = False):
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if new_console else 0
    return subprocess.Popen(argv, creationflags=flags)


@dataclass
class Context:
    settings: Settings
    adb: Any                    # jarvis.services.adb.AdbClient
    reminders: Any              # jarvis.services.reminders.ReminderStore
    llm: Any = None             # jarvis.services.llm.LocalLLM
    speaker: Any = None         # jarvis.services.tts.Speaker
    media_keys: Any = None      # jarvis.services.media_keys module (Windows)
    health: Callable[[], dict] | None = None
    open_url: Callable[[str], Any] = webbrowser.open
    launch: Callable[..., Any] = launch_process
    extras: dict = field(default_factory=dict)

    def phone_ready(self) -> bool:
        return bool(self.settings.phone_control and self.adb and self.adb.is_connected())
