from __future__ import annotations

import pytest

import jarvis.skills  # noqa: F401  (registers commands)
from jarvis.config import Settings
from jarvis.core.assistant import Assistant
from jarvis.core.context import Context
from jarvis.core.events import EventBus
from jarvis.services.reminders import ReminderStore


class FakeAdb:
    """Records phone actions instead of running adb."""

    def __init__(self, connected=True):
        self.connected = connected
        self.calls = []
        self.packages = {"com.whatsapp", "com.instagram.android", "com.example.notesapp"}

    def is_connected(self):
        return self.connected

    def launch(self, package):
        self.calls.append(("launch", package))

    def start_activity(self, *args):
        self.calls.append(("activity", *args))

    def view(self, url, package=None):
        self.calls.append(("view", url, package))

    def dial(self, number):
        self.calls.append(("dial", number))

    def keyevent(self, key):
        self.calls.append(("key", key))

    def installed_packages(self):
        return set(self.packages)

    def shell(self, *args, timeout=20):
        self.calls.append(("shell", *args))
        return (
            "Row: 0 display_name=Mom, data1=+91 98765 43210\n"
            "Row: 1 display_name=Rahul Sharma, data1=9876500000\n"
            "Row: 2 display_name=Rahul Verma, data1=9876511111\n"
        )

    def status(self):
        return {"connected": self.connected, "device": "fake", "message": "fake"}


class FakeLLM:
    def __init__(self):
        self.prompts = []

    def chat(self, text):
        self.prompts.append(("chat", text))
        return f"LLM: {text}"

    def study(self, question):
        self.prompts.append(("study", question))
        return f"STUDY: {question}"


class FakeMediaKeys:
    def __init__(self):
        self.pressed = []

    def press(self, action, times=1):
        self.pressed.append((action, times))


@pytest.fixture
def ctx(tmp_path):
    urls, launched = [], []
    context = Context(
        settings=Settings(multi_task_delay=0, data_dir=str(tmp_path)),
        adb=FakeAdb(),
        reminders=ReminderStore(tmp_path / "reminders.json"),
        llm=FakeLLM(),
        media_keys=FakeMediaKeys(),
        open_url=urls.append,
        launch=lambda argv, new_console=False: launched.append(argv),
    )
    context.extras.update(urls=urls, launched=launched)
    return context


@pytest.fixture
def assistant(ctx):
    bot = Assistant(ctx, EventBus())
    yield bot
    bot.shutdown()


@pytest.fixture
def run(assistant):
    def _run(text):
        return list(assistant.process(text))

    return _run
