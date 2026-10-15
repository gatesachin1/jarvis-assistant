"""Laptop media and volume keys via the Windows keybd_event API (no extra packages)."""

from __future__ import annotations

import sys

from jarvis.core.errors import JarvisError

VK = {
    "play": 0xB3,
    "pause": 0xB3,
    "resume": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
    "toggle": 0xB3,
}
KEYEVENTF_KEYUP = 0x0002


def press(action: str, times: int = 1) -> None:
    if sys.platform != "win32":
        raise JarvisError("Laptop media keys are only supported on Windows.")

    import ctypes

    code = VK[action]
    for _ in range(times):
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)
