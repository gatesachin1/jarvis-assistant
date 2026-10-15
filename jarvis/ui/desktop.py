"""CustomTkinter desktop window.

Tk is not thread-safe, so background threads never touch widgets: events from
the bus go into a queue that the Tk main loop drains every 50 ms.
"""

from __future__ import annotations

import logging
import queue
import webbrowser
from datetime import datetime

import customtkinter as ctk

from jarvis.core.assistant import Assistant
from jarvis.core.events import EventBus
from jarvis.ui.tray import Tray

log = logging.getLogger(__name__)

BG_COLOR = "#070B16"
PANEL_COLOR = "#101A2B"
CARD_COLOR = "#152238"
CYAN = "#00E5FF"
PURPLE = "#A78BFA"
GREEN = "#34D399"
YELLOW = "#FBBF24"
TEXT_COLOR = "#F1F5F9"
MUTED_COLOR = "#94A3B8"

STATE_COLORS = {"idle": GREEN, "busy": YELLOW, "listening": CYAN}

QUICK_ACTIONS = [
    ("⏰ Reminders", "show my reminders"),
    ("📅 Plan My Day", "plan my day"),
    ("📚 Study Mode", "help me study"),
    ("🩺 System Check", "system status"),
    ("📱 WhatsApp", "open whatsapp"),
    ("🎵 Spotify", "open spotify"),
    ("⏯ Play / Pause", "play pause"),
    ("❓ Help", "what can you do"),
]


class DesktopApp:
    def __init__(
        self,
        assistant: Assistant,
        bus: EventBus,
        wake_listener=None,
        dashboard_url: str | None = None,
        start_minimized: bool = False,
    ):
        self.assistant = assistant
        self.speaker = assistant.ctx.speaker
        self.wake = wake_listener
        self.dashboard_url = dashboard_url
        self._events: queue.Queue = queue.Queue()
        self._history: list[str] = []
        self._history_index = 0
        self._hidden_hint_shown = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("J.A.R.V.I.S - Personal AI Command Center")
        self.root.configure(fg_color=BG_COLOR)
        self.root.geometry("1100x780")
        self.root.minsize(850, 650)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_or_close)
        self._set_window_icon()

        self._build_header()
        self._build_actions()
        self._build_chat()
        self._build_input()

        bus.subscribe(self._events.put)
        self.root.after(50, self._pump_events)
        self.root.after(0, self._tick_clock)
        self.entry.focus_set()

        # Tray callbacks run on another thread: they only post to the event queue.
        self.tray = Tray(
            on_show=lambda: self._events.put({"type": "ui", "action": "show"}),
            on_quit=lambda: self._events.put({"type": "ui", "action": "quit"}),
            on_dashboard=(lambda: webbrowser.open(dashboard_url)) if dashboard_url else None,
            speaker=self.speaker,
        )
        has_tray = self.tray.start()

        if start_minimized and has_tray:
            self.root.withdraw()

    def _set_window_icon(self):
        try:
            from PIL import ImageTk

            from jarvis.ui.icon import make_icon

            self._icon_image = ImageTk.PhotoImage(make_icon(64))
            self.root.iconphoto(True, self._icon_image)
            # CustomTkinter resets the icon shortly after start-up; set it again.
            self.root.after(300, lambda: self.root.iconphoto(True, self._icon_image))
        except Exception:
            log.debug("Window icon unavailable", exc_info=True)

    def notify(self, message: str) -> None:
        """Windows toast, used for reminders. Safe to call from any thread."""

        self.tray.notify(message)

    # ---------------------------------------------------------------- layout

    def _build_header(self):
        header = ctk.CTkFrame(self.root, fg_color=PANEL_COLOR, corner_radius=18, border_width=1, border_color=CYAN)
        header.pack(fill="x", padx=20, pady=(20, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=12)
        ctk.CTkLabel(title_box, text="J.A.R.V.I.S", font=("Consolas", 30, "bold"), text_color=CYAN).pack(anchor="w")
        ctk.CTkLabel(
            title_box, text="PERSONAL AI COMMAND CENTER", font=("Consolas", 11), text_color=MUTED_COLOR
        ).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=20)
        self.clock_label = ctk.CTkLabel(right, text="", font=("Consolas", 20, "bold"), text_color=TEXT_COLOR)
        self.clock_label.pack(anchor="e")
        self.status_label = ctk.CTkLabel(
            right, text="● SYSTEM ONLINE", font=("Consolas", 12, "bold"), text_color=GREEN
        )
        self.status_label.pack(anchor="e")

    def _build_actions(self):
        frame = ctk.CTkFrame(self.root, fg_color="#0B1930", corner_radius=15)
        frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            frame, text="QUICK ACTIONS", font=("Consolas", 13, "bold"), text_color=CYAN
        ).pack(anchor="w", padx=15, pady=(10, 4))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=(0, 10))

        columns = 4
        for index, (label, command_text) in enumerate(QUICK_ACTIONS):
            ctk.CTkButton(
                grid,
                text=label,
                height=36,
                font=("Arial", 12, "bold"),
                fg_color="#123453",
                hover_color="#087EAD",
                corner_radius=8,
                command=lambda cmd=command_text: self.assistant.submit(cmd, source="button"),
            ).grid(row=index // columns, column=index % columns, padx=5, pady=5, sticky="ew")

        for column in range(columns):
            grid.grid_columnconfigure(column, weight=1)

    def _build_chat(self):
        self.chat = ctk.CTkTextbox(
            self.root, font=("Segoe UI", 14), corner_radius=12, fg_color="#0B1528",
            text_color="#E8F1FF", wrap="word",
        )
        self.chat.pack(fill="both", expand=True, padx=20, pady=5)
        self.chat.tag_config("jarvis", foreground=CYAN)
        self.chat.tag_config("user", foreground=PURPLE)
        self.chat.tag_config("time", foreground="#64748B")
        self.chat.configure(state="disabled")

    def _build_input(self):
        row = ctk.CTkFrame(self.root, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(5, 20))

        self.entry = ctk.CTkEntry(
            row, placeholder_text="Ask JARVIS... e.g. open Instagram on my phone, remind me to study at 7 pm",
            height=45, font=("Arial", 14),
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self._send)
        self.entry.bind("<Up>", lambda e: self._recall(-1))
        self.entry.bind("<Down>", lambda e: self._recall(1))
        self.entry.bind("<Escape>", lambda e: self.speaker and self.speaker.stop())

        ctk.CTkButton(row, text="SEND", width=80, height=45, command=self._send).pack(side="left", padx=(0, 8))

        self.mic_button = ctk.CTkButton(
            row, text="🎤", width=55, height=45, command=self.assistant.listen_async
        )
        self.mic_button.pack(side="left", padx=(0, 8))

        self.voice_button = ctk.CTkButton(row, text="🔊", width=55, height=45, command=self._toggle_voice)
        self.voice_button.pack(side="left")
        self._refresh_voice_button()

    # -------------------------------------------------------------- behaviour

    def _send(self, _event=None):
        text = self.entry.get().strip()
        if not text:
            return
        self._history.append(text)
        self._history_index = len(self._history)
        self.entry.delete(0, "end")
        self.assistant.submit(text, source="text")

    def _recall(self, step):
        if not self._history:
            return
        self._history_index = max(0, min(len(self._history), self._history_index + step))
        self.entry.delete(0, "end")
        if self._history_index < len(self._history):
            self.entry.insert(0, self._history[self._history_index])

    def _toggle_voice(self):
        if self.speaker:
            self.speaker.set_enabled(not self.speaker.enabled)
        self._refresh_voice_button()

    def _refresh_voice_button(self):
        on = bool(self.speaker and self.speaker.enabled)
        self.voice_button.configure(text="🔊" if on else "🔇", fg_color="#1F6AA5" if on else "#3A3F4B")

    def _tick_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("%I:%M:%S %p"))
        self.root.after(1000, self._tick_clock)

    def _pump_events(self):
        try:
            while True:
                self._handle(self._events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(50, self._pump_events)

    def _handle(self, event):
        if event["type"] == "ui":
            if event["action"] == "show":
                self.show()
            elif event["action"] == "quit":
                self.close()
        elif event["type"] == "message":
            self._append(event["sender"], event["text"])
        elif event["type"] == "status":
            color = STATE_COLORS.get(event["state"], GREEN)
            self.status_label.configure(text=f"● {event['text']}", text_color=color)
            self.mic_button.configure(fg_color=CYAN if event["state"] == "listening" else "#1F6AA5")
            self._refresh_voice_button()

    def _append(self, sender, text):
        name, tag = ("JARVIS", "jarvis") if sender == "jarvis" else ("YOU", "user")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{datetime.now():%H:%M}  ", "time")
        self.chat.insert("end", f"{name}: ", tag)
        self.chat.insert("end", f"{text}\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def run(self):
        self.root.mainloop()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.entry.focus_set()

    def hide_or_close(self):
        """Window X button: keep running in the tray if there is one."""

        if not self.tray.running:
            self.close()
            return
        self.root.withdraw()
        if not self._hidden_hint_shown:
            self._hidden_hint_shown = True
            self.tray.notify("Still running in the tray. Right-click the J icon to quit.")

    def close(self):
        self.tray.stop()
        if self.wake:
            self.wake.stop()
        if self.speaker:
            self.speaker.stop()
        self.assistant.shutdown()
        self.root.destroy()
