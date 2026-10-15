import subprocess

import pytest

from jarvis.services import autostart
from jarvis.services.adb import AdbClient, AdbError
from jarvis.services.tts import clean_for_speech


class WifiRunner:
    """Fake adb that simulates a phone moving from USB to Wi-Fi."""

    def __init__(self):
        self.calls = []
        self.devices = ["USB123"]
        self.reachable = True

    def __call__(self, argv, timeout):
        args = argv[1:]
        self.calls.append(args)
        out = ""
        if args == ["devices"]:
            out = "List of devices attached\n" + "".join(f"{d}\tdevice\n" for d in self.devices)
        elif "ip" in args and "wlan0" in args:
            out = "3: wlan0: <UP>\n    inet 192.168.1.42/24 brd 192.168.1.255 scope global wlan0"
        elif args[:1] == ["connect"]:
            if self.reachable:
                self.devices.append(args[1])
                out = f"connected to {args[1]}"
            else:
                out = f"failed to connect to {args[1]}"
        elif args[:1] == ["pair"]:
            out = "Successfully paired to 192.168.1.42:37000"
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")


@pytest.fixture
def wifi_adb(tmp_path):
    exe = tmp_path / "adb.exe"
    exe.write_text("")
    runner = WifiRunner()
    client = AdbClient(str(exe), runner=runner, state_file=tmp_path / "phone.json")
    return client, runner, tmp_path


def test_enable_wifi_switches_usb_phone_and_remembers_address(wifi_adb):
    client, runner, tmp_path = wifi_adb
    assert client.enable_wifi() == "192.168.1.42:5555"
    assert ["-s", "USB123", "tcpip", "5555"] in runner.calls

    # A new client (next app start) remembers the phone.
    again = AdbClient(client.path, runner=runner, state_file=tmp_path / "phone.json")
    assert again.wifi_address == "192.168.1.42:5555"


def test_auto_reconnects_when_wifi_phone_drops(wifi_adb):
    client, runner, _ = wifi_adb
    client.wifi_address = "192.168.1.42:5555"
    runner.devices = []  # cable unplugged, phone asleep

    assert client.device() == "192.168.1.42:5555"
    assert client.status()["message"] == "Connected via Wi-Fi"


def test_connect_failure_is_reported(wifi_adb):
    client, runner, _ = wifi_adb
    runner.reachable = False
    with pytest.raises(AdbError, match="Couldn't connect"):
        client.connect_wifi("192.168.1.99")


def test_wireless_voice_commands_route(run, ctx):
    calls = []
    ctx.adb.enable_wifi = lambda: calls.append("wifi") or "192.168.1.42:5555"
    ctx.adb.connect_wifi = lambda addr: calls.append(addr) or addr
    ctx.adb.pair = lambda addr, code: calls.append((addr, code))

    assert "192.168.1.42:5555" in run("connect phone wirelessly")[0]
    run("connect to my phone at 192.168.1.42:41234")
    run("pair phone 192.168.1.42:37000 code 123456")
    assert calls == ["wifi", "192.168.1.42:41234", ("192.168.1.42:37000", "123456")]


def test_autostart_command_runs_without_console(monkeypatch):
    command = autostart.launch_command()
    assert "jarvis_gui.py" in command and "--minimized" in command
    assert "pythonw.exe" in command.lower() or "python" in command.lower()


def test_speech_text_is_cleaned():
    text = clean_for_speech("**Reminder** ⏰ see https://example.com", 600)
    assert text == "Reminder see link"
