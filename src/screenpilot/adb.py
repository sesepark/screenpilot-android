from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from .errors import AdbError


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    state: str
    description: str = ""


class AdbDevice:
    """ADB transport that never touches the macOS mouse or window focus."""

    def __init__(self, serial: str | None = None, adb_path: str = "adb", timeout: float = 15):
        resolved = shutil.which(adb_path) if "/" not in adb_path else adb_path
        if not resolved:
            raise AdbError(
                "adb was not found. Install Android SDK Platform-Tools and add it to PATH."
            )
        self.adb_path = resolved
        self.serial = serial
        self.timeout = timeout

    def _command(self, args: Sequence[str]) -> list[str]:
        command = [self.adb_path]
        if self.serial:
            command += ["-s", self.serial]
        return command + list(args)

    def _run(self, args: Sequence[str], *, binary: bool = False) -> bytes | str:
        command = self._command(args)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB timed out after {self.timeout:g}s: {' '.join(command)}") from exc
        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace").strip()
            raise AdbError(f"ADB failed ({result.returncode}): {detail or 'unknown error'}")
        return result.stdout if binary else result.stdout.decode(errors="replace")

    @classmethod
    def list_devices(cls, adb_path: str = "adb") -> list[DeviceInfo]:
        resolved = shutil.which(adb_path) if "/" not in adb_path else adb_path
        if not resolved:
            raise AdbError("adb was not found in PATH")
        result = subprocess.run(
            [resolved, "devices", "-l"], check=False, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise AdbError(result.stderr.strip() or "adb devices failed")
        devices: list[DeviceInfo] = []
        for line in result.stdout.splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split(maxsplit=2)
            devices.append(
                DeviceInfo(
                    parts[0],
                    parts[1] if len(parts) > 1 else "unknown",
                    parts[2] if len(parts) > 2 else "",
                )
            )
        return devices

    def screenshot(self) -> np.ndarray:
        payload = self._run(["exec-out", "screencap", "-p"], binary=True)
        encoded = np.frombuffer(payload, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise AdbError("Emulator returned an invalid PNG screenshot")
        return image

    def tap(self, x: int, y: int) -> None:
        self._run(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self._run(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)])

    def keyevent(self, keycode: str) -> None:
        self._run(["shell", "input", "keyevent", keycode])
