import subprocess

import pytest

from jarvis.services.adb import AdbClient, AdbError


class Runner:
    def __init__(self, devices="List of devices attached\nABC123\tdevice\n"):
        self.devices = devices
        self.calls = []

    def __call__(self, argv, timeout):
        self.calls.append(argv[1:])
        stdout = self.devices if argv[1:] == ["devices"] else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


@pytest.fixture
def adb(tmp_path):
    exe = tmp_path / "adb.exe"
    exe.write_text("")
    runner = Runner()
    client = AdbClient(str(exe), runner=runner)
    client.runner = runner
    return client


def test_shell_arguments_are_quoted_against_injection(adb):
    adb.input_text("rock & roll; reboot")
    assert adb.runner.calls[-1] == ["-s", "ABC123", "shell", "input", "text", "'rock%s&%sroll;%sreboot'"]


def test_urls_with_ampersands_survive(adb):
    adb.view("https://wa.me/91?text=a&b", "com.whatsapp")
    assert "'https://wa.me/91?text=a&b'" in adb.runner.calls[-1]


def test_device_is_cached(adb):
    adb.keyevent("KEYCODE_MEDIA_PAUSE")
    adb.keyevent("KEYCODE_MEDIA_PLAY")
    assert adb.runner.calls.count(["devices"]) == 1


def test_unauthorized_phone_gives_helpful_error(tmp_path):
    exe = tmp_path / "adb.exe"
    exe.write_text("")
    client = AdbClient(str(exe), runner=Runner("List of devices attached\nABC\tunauthorized\n"))
    with pytest.raises(AdbError, match="not authorised"):
        client.device()


def test_missing_adb_is_reported(tmp_path):
    client = AdbClient(str(tmp_path / "missing.exe"))
    assert not client.is_connected()
    with pytest.raises(AdbError, match="ADB was not found"):
        client.run("devices")
