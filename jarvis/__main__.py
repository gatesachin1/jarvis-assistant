"""Start JARVIS.

    python -m jarvis                 desktop app
    python -m jarvis --web           desktop app + web dashboard
    python -m jarvis --headless      web dashboard only (no desktop window)
    python -m jarvis --no-wake       skip "Hey JARVIS" wake word
    python -m jarvis --mute          no spoken replies
    python -m jarvis --minimized     start hidden in the system tray
    python -m jarvis --install-startup / --remove-startup
"""

from __future__ import annotations

import argparse
import logging
import threading
import webbrowser
from pathlib import Path

from jarvis import __version__
from jarvis.config import ROOT_DIR, load_settings
from jarvis.core.assistant import Assistant
from jarvis.core.context import Context
from jarvis.core.events import EventBus
from jarvis.logging_setup import setup_logging
from jarvis.services import health
from jarvis.services.adb import AdbClient
from jarvis.services.llm import LocalLLM
from jarvis.services.reminders import ReminderScheduler, ReminderStore
from jarvis.services.tts import Speaker

log = logging.getLogger("jarvis")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="jarvis", description="J.A.R.V.I.S personal assistant")
    parser.add_argument("--web", action="store_true", help="also start the web dashboard")
    parser.add_argument("--headless", action="store_true", help="web dashboard only, no desktop window")
    parser.add_argument("--port", type=int, help="web dashboard port")
    parser.add_argument("--no-wake", action="store_true", help="disable the 'Hey JARVIS' wake word")
    parser.add_argument("--mute", action="store_true", help="disable spoken replies")
    parser.add_argument("--no-browser", action="store_true", help="don't open the dashboard in a browser")
    parser.add_argument("--minimized", action="store_true", help="start hidden in the system tray")
    parser.add_argument("--install-startup", action="store_true", help="start JARVIS when Windows starts, then exit")
    parser.add_argument("--remove-startup", action="store_true", help="stop starting with Windows, then exit")
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"J.A.R.V.I.S {__version__}")
    return parser.parse_args(argv)


def build(settings):
    """Create the shared services. Kept separate from main() for scripting/tests."""

    bus = EventBus()
    speaker = Speaker(
        rate=settings.tts_rate,
        enabled=settings.tts_enabled,
        max_chars=settings.tts_max_chars,
        engine=settings.tts_engine,
        piper_voice=settings.piper_voice,
        models_dir=settings.models_dir,
    )

    ctx = Context(
        settings=settings,
        adb=AdbClient(
            settings.adb_path,
            settings.adb_serial,
            enabled=settings.phone_control,
            wifi_address=settings.adb_wifi_address,
            state_file=Path(settings.data_dir) / "phone.json",
        ),
        reminders=ReminderStore(
            Path(settings.data_dir) / "reminders.json",
            legacy_path=ROOT_DIR / "jarvis_reminders.json",
        ),
        llm=LocalLLM(settings.ollama_model),
        speaker=speaker,
    )
    ctx.health = lambda: health.collect(ctx)

    import jarvis.skills  # noqa: F401  (registers all commands)

    return Assistant(ctx, bus), bus


def main(argv=None):
    args = parse_args(argv)

    if args.install_startup or args.remove_startup:
        from jarvis.services import autostart

        if args.install_startup:
            print("JARVIS will start with Windows:\n  " + autostart.enable())
        else:
            autostart.disable()
            print("JARVIS will no longer start with Windows.")
        return

    settings = load_settings()

    if args.port:
        settings.web_port = args.port
    if args.mute:
        settings.tts_enabled = False
    if args.no_wake:
        settings.wake_word = False

    setup_logging(settings.log_dir, args.verbose)
    log.info("Starting J.A.R.V.I.S %s", __version__)

    assistant, bus = build(settings)

    desktop = None  # set below; reminders also raise a Windows toast through its tray icon

    def on_reminder(reminder):
        assistant.say(f"⏰ Reminder: {reminder.task}")
        if desktop:
            desktop.notify(f"⏰ {reminder.task}")

    # Reminders fire even when nobody is looking at the window.
    ReminderScheduler(assistant.ctx.reminders, on_reminder).start()

    # Load the offline voice models in the background so the first reply/command is quick.
    if settings.tts_enabled:
        assistant.ctx.speaker.start()
    if settings.stt_engine == "whisper":
        from jarvis.services import stt

        def warm_whisper():
            try:
                stt.load_whisper(settings.whisper_model, settings.models_dir)
            except Exception:
                log.exception("Whisper unavailable; voice input will use Google")

        threading.Thread(target=warm_whisper, name="jarvis-whisper", daemon=True).start()

    wake = None
    if settings.wake_word:
        from jarvis.services.wakeword import WakeWordListener

        wake = WakeWordListener(
            settings.wake_word_model,
            settings.wake_word_threshold,
            on_wake=assistant.listen_async,
            on_status=lambda text: assistant.status("idle", text),
            is_suppressed=lambda: assistant.ctx.speaker.speaking,
        )
        assistant.before_listen = wake.pause
        assistant.after_listen = wake.resume
        wake.start()

    def greet():
        info = health.collect(assistant.ctx)
        hello = "Hello! I am JARVIS. Say 'what can you do' to see my commands."
        if args.minimized:  # silent start at Windows sign-in
            assistant.bus.publish({"type": "message", "sender": "jarvis", "source": "jarvis", "text": hello})
        else:
            assistant.say(hello)
        problems = health.summary(info).splitlines()
        problems = [line for line in problems if "Not ready" in line]
        if problems:
            assistant.bus.publish(
                {"type": "message", "sender": "jarvis", "source": "jarvis",
                 "text": "Heads up:\n" + "\n".join(problems)}
            )

    threading.Thread(target=greet, name="jarvis-greet", daemon=True).start()

    url = f"http://{settings.web_host}:{settings.web_port}"

    if args.web or args.headless:
        from jarvis.web.server import serve

        if not (args.no_browser or args.minimized):
            threading.Timer(1.5, webbrowser.open, args=[url]).start()
        serve(assistant, bus, settings.web_host, settings.web_port, background=not args.headless)

    if args.headless:
        return  # serve() blocked until Ctrl+C

    from jarvis.ui.desktop import DesktopApp

    desktop = DesktopApp(
        assistant,
        bus,
        wake_listener=wake,
        dashboard_url=url if args.web else None,
        start_minimized=args.minimized,
    )
    desktop.run()


if __name__ == "__main__":
    main()
