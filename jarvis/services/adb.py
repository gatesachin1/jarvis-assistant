"""Android Debug Bridge client.

Every phone action goes through this one class, so the ADB path, device choice,
timeouts and error messages are handled in one place.

`adb shell a b c` joins its arguments into a single command line that the
phone's shell parses again, so every argument is quoted with shlex.quote.
Without that, a song name like "rock & roll" or a message containing ";"
would be interpreted as shell syntax on the phone.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable

from jarvis.core.errors import JarvisError

log = logging.getLogger(__name__)

DEVICE_CACHE_SECONDS = 10
PACKAGE_CACHE_SECONDS = 300
WIFI_RETRY_SECONDS = 30
WIFI_PORT = 5555


class AdbError(JarvisError):
    pass


def _default_runner(argv, timeout):
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class AdbClient:
    def __init__(
        self,
        path: str,
        serial: str = "",
        enabled: bool = True,
        runner: Callable = _default_runner,
        wifi_address: str = "",
        state_file: str | os.PathLike | None = None,
    ):
        self.path = path
        self.serial = serial
        self.enabled = enabled
        self._runner = runner
        self._state_file = state_file
        self.wifi_address = wifi_address or self._load_state().get("wifi_address", "")
        self._wifi_attempted = 0.0
        self._lock = threading.Lock()
        self._device: str | None = None
        self._device_checked = 0.0
        self._packages: set[str] | None = None
        self._packages_checked = 0.0

    # ------------------------------------------------------------- low level

    def available(self) -> bool:
        return bool(self.enabled and self.path and os.path.isfile(self.path))

    def run(self, *args: str, timeout: float = 20) -> str:
        if not self.enabled:
            raise AdbError("Phone control is turned off in config.json (phone_control).")

        if not self.available():
            raise AdbError(
                "ADB was not found. Install Android platform-tools and set "
                "adb_path in config.json, or add adb to PATH."
            )

        argv = [self.path, *map(str, args)]
        log.debug("ADB %s", argv[1:])

        try:
            result = self._runner(argv, timeout)
        except subprocess.TimeoutExpired:
            self.forget_device()
            raise AdbError("The phone did not respond in time.") from None

        if result.returncode != 0:
            self.forget_device()
            raise AdbError((result.stderr or result.stdout or "ADB command failed.").strip())

        return (result.stdout or "").strip()

    def _list_devices(self) -> tuple[list[str], bool]:
        devices, unauthorized = [], False
        for line in self.run("devices").splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                if parts[1] == "device":
                    devices.append(parts[0])
                elif parts[1] == "unauthorized":
                    unauthorized = True
        if self.serial:
            devices = [d for d in devices if d == self.serial]
        return devices, unauthorized

    def device(self) -> str:
        with self._lock:
            fresh = time.monotonic() - self._device_checked < DEVICE_CACHE_SECONDS
            if self._device and fresh:
                return self._device

        devices, unauthorized = self._list_devices()

        # Phone dropped off Wi-Fi (sleep, router change)? Reconnect quietly.
        if not devices and self.wifi_address and time.monotonic() - self._wifi_attempted > WIFI_RETRY_SECONDS:
            self._wifi_attempted = time.monotonic()
            try:
                self.connect_wifi(self.wifi_address, remember=False)
                devices, unauthorized = self._list_devices()
            except AdbError as error:
                log.info("Wi-Fi reconnect to %s failed: %s", self.wifi_address, error)

        if not devices:
            if unauthorized:
                raise AdbError("Your phone is connected but not authorised. Accept the USB debugging prompt on the phone.")
            raise AdbError(
                "No Android phone found. Connect it by USB (with USB debugging on) "
                "or say 'connect phone wirelessly' while it's plugged in."
            )

        with self._lock:
            self._device = devices[0]
            self._device_checked = time.monotonic()
            return self._device

    # ---------------------------------------------------------------- Wi-Fi

    def _load_state(self) -> dict:
        try:
            return json.loads(open(self._state_file, encoding="utf-8").read()) if self._state_file else {}
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        if not self._state_file:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self._state_file)), exist_ok=True)
        with open(self._state_file, "w", encoding="utf-8") as file:
            json.dump({"wifi_address": self.wifi_address}, file)

    def connect_wifi(self, address: str, remember: bool = True) -> str:
        if ":" not in address:
            address = f"{address}:{WIFI_PORT}"
        try:
            output = self.run("connect", address, timeout=15)
        except AdbError as error:
            output = str(error)
        if "connected to" not in output:  # covers "already connected to"
            raise AdbError(f"Couldn't connect to the phone at {address}: {output or 'no response'}")
        self.forget_device()
        if remember:
            self.wifi_address = address
            self._save_state()
        return address

    def pair(self, address: str, code: str) -> None:
        """Android 11+ 'Wireless debugging' pairing (no USB cable needed at all)."""

        output = self.run("pair", address, code, timeout=30)
        if "Successfully paired" not in output:
            raise AdbError(f"Pairing failed: {output}")

    def enable_wifi(self) -> str:
        """Switch a USB-connected phone to Wi-Fi debugging and connect to it."""

        devices, _ = self._list_devices()
        usb = [d for d in devices if ":" not in d and not d.startswith("emulator")]
        if not usb:
            raise AdbError("Plug the phone in by USB once so I can switch it to Wi-Fi.")

        output = self.run("-s", usb[0], "shell", "ip", "-f", "inet", "addr", "show", "wlan0")
        match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", output)
        if not match:
            raise AdbError("Your phone isn't on Wi-Fi. Connect it to the same Wi-Fi as this PC.")

        self.run("-s", usb[0], "tcpip", str(WIFI_PORT))
        time.sleep(2)  # adbd restarts in TCP mode
        return self.connect_wifi(f"{match.group(1)}:{WIFI_PORT}")

    def disconnect_wifi(self) -> None:
        if self.wifi_address:
            try:
                self.run("disconnect", self.wifi_address)
            except AdbError:
                pass
        self.wifi_address = ""
        self._save_state()
        self.forget_device()

    def forget_device(self) -> None:
        with self._lock:
            self._device = None
            self._device_checked = 0.0

    def is_connected(self) -> bool:
        if not self.available():
            return False
        try:
            self.device()
            return True
        except AdbError:
            return False

    def shell(self, *args: str, timeout: float = 20) -> str:
        quoted = [shlex.quote(str(arg)) for arg in args]
        return self.run("-s", self.device(), "shell", *quoted, timeout=timeout)

    # ----------------------------------------------------------- app actions

    def launch(self, package: str) -> None:
        output = self.shell(
            "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"
        )
        if "No activities found" in output or "monkey aborted" in output:
            raise AdbError(f"{package} is not installed on your phone.")

    def start_activity(self, *intent_args: str) -> None:
        output = self.shell("am", "start", *intent_args)
        if re.search(r"^Error", output, re.M):
            raise AdbError(output.splitlines()[-1])

    def view(self, url: str, package: str | None = None) -> None:
        args = ["-a", "android.intent.action.VIEW", "-d", url]
        if package:
            args += ["-p", package]
        self.start_activity(*args)

    def dial(self, number: str) -> None:
        self.start_activity("-a", "android.intent.action.DIAL", "-d", f"tel:{number}")

    def keyevent(self, key: str | int) -> None:
        self.shell("input", "keyevent", str(key), timeout=10)

    def tap(self, x: int, y: int) -> None:
        self.shell("input", "tap", str(x), str(y), timeout=10)

    def input_text(self, text: str) -> None:
        """Type into the focused field. `input text` uses %s for spaces."""

        if not text.isascii():
            raise AdbError("The phone keyboard can only type English characters via ADB.")
        self.shell("input", "text", text.replace(" ", "%s"), timeout=15)

    # ----------------------------------------------------------- inspection

    def installed_packages(self) -> set[str]:
        with self._lock:
            if self._packages and time.monotonic() - self._packages_checked < PACKAGE_CACHE_SECONDS:
                return set(self._packages)

        output = self.shell(
            "cmd", "package", "query-activities", "--brief",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            timeout=30,
        )
        packages = {
            line.split("/", 1)[0].strip()
            for line in output.splitlines()
            if "/" in line and not line.startswith("No activities")
        }

        with self._lock:
            self._packages = packages
            self._packages_checked = time.monotonic()
        return set(packages)

    def dump_ui(self) -> ET.Element:
        self.shell("uiautomator", "dump", "/sdcard/jarvis_window.xml", timeout=30)
        xml_text = self.shell("cat", "/sdcard/jarvis_window.xml", timeout=15)
        try:
            return ET.fromstring(xml_text[xml_text.find("<"):])
        except ET.ParseError:
            raise AdbError("I couldn't read the phone screen.") from None

    def tap_node(self, keywords: list[str]) -> bool:
        """Tap the first on-screen element whose text/description/id contains a keyword."""

        keywords = [k.lower() for k in keywords]

        for node in self.dump_ui().iter("node"):
            label = " ".join(
                node.attrib.get(key, "") for key in ("text", "content-desc", "resource-id")
            ).lower()

            if any(keyword in label for keyword in keywords):
                numbers = re.findall(r"\d+", node.attrib.get("bounds", ""))
                if len(numbers) == 4:
                    x1, y1, x2, y2 = map(int, numbers)
                    self.tap((x1 + x2) // 2, (y1 + y2) // 2)
                    return True

        return False

    def status(self) -> dict:
        if not self.enabled:
            return {"connected": False, "device": None, "message": "Phone control disabled"}
        if not self.available():
            return {"connected": False, "device": None, "message": "ADB not found"}
        try:
            device = self.device()
            via = "Wi-Fi" if ":" in device else "USB"
            return {"connected": True, "device": device, "message": f"Connected via {via}"}
        except AdbError as error:
            return {"connected": False, "device": None, "message": str(error)}
