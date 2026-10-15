"""System tray icon and Windows notifications (pystray).

Menu callbacks run on the tray thread, so they only post requests; the
desktop window acts on them from the Tk thread.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from jarvis.services import autostart

log = logging.getLogger(__name__)


class Tray:
    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_dashboard: Callable[[], None] | None = None,
        speaker=None,
    ):
        self.on_show = on_show
        self.on_quit = on_quit
        self.on_dashboard = on_dashboard
        self.speaker = speaker
        self._icon = None

    @property
    def running(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        try:
            import pystray

            from jarvis.ui.icon import make_icon
        except ImportError:
            log.info("pystray/Pillow not installed: no tray icon")
            return False

        item = pystray.MenuItem
        items = [item("Open JARVIS", lambda: self.on_show(), default=True)]
        if self.on_dashboard:
            items.append(item("Open web dashboard", lambda: self.on_dashboard()))
        items += [
            pystray.Menu.SEPARATOR,
            item(
                "Voice replies",
                self._toggle_voice,
                checked=lambda _: bool(self.speaker and self.speaker.enabled),
                enabled=self.speaker is not None,
            ),
            item("Start with Windows", self._toggle_autostart, checked=lambda _: autostart.is_enabled()),
            pystray.Menu.SEPARATOR,
            item("Quit JARVIS", lambda: self.on_quit()),
        ]

        self._icon = pystray.Icon("JARVIS", make_icon(64), "J.A.R.V.I.S", pystray.Menu(*items))
        threading.Thread(target=self._icon.run, name="jarvis-tray", daemon=True).start()
        return True

    def _toggle_voice(self, *_):
        if self.speaker:
            self.speaker.set_enabled(not self.speaker.enabled)

    def _toggle_autostart(self, *_):
        try:
            autostart.disable() if autostart.is_enabled() else autostart.enable()
        except Exception:
            log.exception("Could not change start-with-Windows")

    def notify(self, message: str, title: str = "J.A.R.V.I.S") -> None:
        """Show a Windows notification (silently ignored without a tray icon)."""

        if self._icon is None:
            return
        try:
            self._icon.notify(message[:250], title)
        except Exception:
            log.debug("Notification failed", exc_info=True)

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
