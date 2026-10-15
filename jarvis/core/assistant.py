"""The command engine shared by the desktop app, web dashboard and voice input."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from jarvis.core import registry
from jarvis.core.context import Context
from jarvis.core.errors import JarvisError
from jarvis.core.events import EventBus
from jarvis.core.text import normalize, split_tasks

log = logging.getLogger(__name__)

IDLE_TEXT = "SYSTEM ONLINE"


class Assistant:
    def __init__(self, ctx: Context, bus: EventBus):
        self.ctx = ctx
        self.bus = bus
        # One worker keeps commands in order ("open X then search Y") and stops
        # a burst of clicks from spawning dozens of threads.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-cmd")
        self._listen_lock = threading.Lock()
        self.before_listen: Callable[[], None] = lambda: None
        self.after_listen: Callable[[], None] = lambda: None

    # ------------------------------------------------------------------ input

    def submit(self, text: str, source: str = "text") -> Future | None:
        """Queue a command from any UI. Returns immediately."""

        text = (text or "").strip()
        if not text:
            return None

        self.bus.publish({"type": "message", "sender": "user", "text": text, "source": source})
        return self._executor.submit(self._run, text)

    def listen_async(self) -> None:
        """Capture one spoken command in the background (mic button / wake word)."""

        threading.Thread(target=self._listen, name="jarvis-listen", daemon=True).start()

    def _listen(self) -> None:
        if not self._listen_lock.acquire(blocking=False):
            return  # already listening

        from jarvis.services import stt

        try:
            self.before_listen()
            self.status("listening", "Listening...")
            text = stt.listen_once(
                self.ctx.settings,
                on_recognizing=lambda: self.status("busy", "Recognizing..."),
            )
            self.submit(text, source="voice")
        except JarvisError as error:
            self.status("idle", str(error))
        except Exception as error:
            log.exception("Voice input failed")
            self.status("idle", f"Voice error: {error}")
        finally:
            self.after_listen()
            self._listen_lock.release()

    # -------------------------------------------------------------- execution

    def _run(self, text: str) -> None:
        self.status("busy", "JARVIS is processing...")
        try:
            for reply in self.process(text):
                self.say(reply)
        except Exception:
            log.exception("Command crashed: %s", text)
            self.say("Something went wrong while running that command.")
        finally:
            self.status("idle", IDLE_TEXT)

    def process(self, text: str):
        """Yield one reply per task. Used directly by tests."""

        tasks = split_tasks(normalize(text), self._is_command, self._is_atomic)
        log.info("Tasks: %s", tasks)

        for index, task in enumerate(tasks):
            if index:
                # Give the phone time to finish the previous action.
                time.sleep(self.ctx.settings.multi_task_delay)
            reply = self.execute(normalize(task))
            if reply:
                yield reply

    def execute(self, task: str) -> str:
        for cmd, request in registry.matches(task):
            try:
                reply = cmd.handler(self.ctx, request)
            except JarvisError as error:
                return str(error)
            except Exception as error:
                log.exception("Command '%s' failed for: %s", cmd.name, task)
                return f"I couldn't complete '{task}': {error}"

            if reply is not None:
                log.info("[%s] %s -> %s", cmd.name, task, reply)
                return reply

        if self.ctx.llm is None:
            return "I don't know how to do that yet."

        return self.ctx.llm.chat(task)

    @staticmethod
    def _is_command(text: str) -> bool:
        return registry.first_match(normalize(text)) is not None

    @staticmethod
    def _is_atomic(text: str) -> bool:
        cmd = registry.first_match(text)
        return bool(cmd and cmd.atomic)

    # ----------------------------------------------------------------- output

    def say(self, text: str) -> None:
        self.bus.publish({"type": "message", "sender": "jarvis", "text": text, "source": "jarvis"})
        if self.ctx.speaker:
            self.ctx.speaker.say(text)

    def status(self, state: str, text: str) -> None:
        self.bus.publish({"type": "status", "state": state, "text": text})

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
