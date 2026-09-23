"""Safe starter extensions for project-specific integration.

This is the intended project-local insertion point. Replace or add classes here,
then reference them from workflow YAML by dotted Python path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from screenpilot.adb import AdbDevice


class CustomBackend(AdbDevice):
    """Starter backend that currently preserves the standard ADB behavior.

    Override screenshot/tap/swipe/keyevent here when integrating another trusted
    capture or input implementation. Keep the signatures defined by
    `screenpilot.extensions.AutomationBackend`.
    """

    def __init__(
        self, serial: str | None = None, adb_path: str = "adb", timeout: float = 15
    ) -> None:
        super().__init__(serial=serial, adb_path=adb_path, timeout=timeout)


class JsonlObserver:
    """Append execution ground-truth events to a JSON Lines file."""

    def __init__(self, path: str = "artifacts/run-events.jsonl") -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def on_event(self, event: Mapping[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(event), ensure_ascii=False, sort_keys=True) + "\n")
