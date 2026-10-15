"""Start JARVIS when Windows starts (per-user Run registry key, no admin needed)."""

from __future__ import annotations

import sys
from pathlib import Path

from jarvis.core.errors import JarvisError

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "JARVIS"


def launch_command() -> str:
    """Command line that starts JARVIS minimised to the tray, without a console window."""

    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized --web --no-browser'

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    script = Path(__file__).resolve().parents[2] / "jarvis_gui.py"
    return f'"{interpreter}" "{script}" --minimized --web --no-browser'


def _winreg():
    if sys.platform != "win32":
        raise JarvisError("Start-with-Windows is only available on Windows.")
    import winreg

    return winreg


def is_enabled() -> bool:
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except (OSError, JarvisError):
        return False


def enable() -> str:
    winreg = _winreg()
    command = launch_command()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    return command


def disable() -> None:
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
