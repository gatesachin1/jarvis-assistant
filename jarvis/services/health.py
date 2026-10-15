"""System health: CPU/RAM, Ollama, phone and microphone status."""

from __future__ import annotations

import threading
import time

_cache: dict = {}
_cache_lock = threading.Lock()
CACHE_SECONDS = 5


def system_usage() -> dict:
    try:
        import psutil

        return {"cpu": psutil.cpu_percent(interval=None), "ram": psutil.virtual_memory().percent}
    except ImportError:
        return {"cpu": None, "ram": None}


def microphone_status() -> dict:
    try:
        import sounddevice as sd

        sd.query_devices(kind="input")
        return {"available": True, "message": "Ready"}
    except ImportError:
        return {"available": False, "message": "sounddevice not installed"}
    except Exception:
        return {"available": False, "message": "No microphone found"}


def collect(ctx) -> dict:
    """Return cached health info (Ollama/ADB checks are slow-ish)."""

    with _cache_lock:
        if _cache and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return {**_cache["data"], **system_usage()}

    data = {
        "llm": ctx.llm.status() if ctx.llm else {"online": False, "message": "Disabled"},
        "phone": ctx.adb.status(),
        "microphone": microphone_status(),
        "voice_output": bool(ctx.speaker and ctx.speaker.enabled),
    }

    with _cache_lock:
        _cache.update(at=time.monotonic(), data=data)

    return {**data, **system_usage()}


def summary(info: dict) -> str:
    def mark(ok):
        return "OK" if ok else "Not ready"

    lines = [
        f"AI model ({info['llm'].get('model', '-')}): {mark(info['llm'].get('model_installed', info['llm'].get('online')))} - {info['llm']['message']}",
        f"Phone: {mark(info['phone']['connected'])} - {info['phone']['message']}",
        f"Microphone: {mark(info['microphone']['available'])} - {info['microphone']['message']}",
    ]
    if info.get("cpu") is not None:
        lines.append(f"CPU {info['cpu']:.0f}% · RAM {info['ram']:.0f}%")
    return "\n".join(lines)
