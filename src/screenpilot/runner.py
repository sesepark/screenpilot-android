from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import WorkflowConfig
from .errors import ConfigError, MatchTimeout
from .extensions import AutomationBackend, NullObserver, RunObserver
from .vision import Match, TemplateMatcher, annotate

LOG = logging.getLogger("screenpilot")


class WorkflowRunner:
    def __init__(
        self,
        config: WorkflowConfig,
        device: AutomationBackend,
        *,
        observer: RunObserver | None = None,
        sleeper=time.sleep,
    ):
        self.config = config
        self.device = device
        self.matcher = TemplateMatcher(config.templates)
        self.observer = observer or NullObserver()
        self.sleeper = sleeper
        self.last_screen: np.ndarray | None = None

    def run(self) -> None:
        self.config.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._emit("run_start", workflow=str(self.config.source))
        try:
            self._run_steps(self.config.steps, "steps")
        except Exception as exc:
            self._emit("run_error", error_type=type(exc).__name__, message=str(exc))
            raise
        self._emit("run_complete")

    def _run_steps(self, steps: list[dict[str, Any]], path: str) -> None:
        for index, step in enumerate(steps):
            action, value = next(iter(step.items()))
            label = f"{path}[{index}].{action}"
            LOG.info("%s", label)
            self._emit("action_start", action=action, path=label)
            if action == "wait_for":
                self._wait_for(value, label)
            elif action == "tap":
                self._tap_template(value, label)
            elif action == "tap_at":
                screen = self.device.screenshot()
                x, y = self._point(value, screen)
                self.device.tap(x, y)
                self._emit("input", kind="tap", x=x, y=y, path=label)
            elif action == "swipe":
                self._swipe(value, label)
            elif action == "sleep":
                self.sleeper(float(value))
            elif action == "keyevent":
                self.device.keyevent(str(value))
                self._emit("input", kind="keyevent", keycode=str(value), path=label)
            elif action == "screenshot":
                self._save_screen(str(value))
            elif action == "repeat":
                self._repeat(value, label)
            else:
                raise ConfigError(f"Unsupported action at {label}")
            self._emit("action_complete", action=action, path=label)

    def _wait_for(self, value: Any, label: str) -> Match:
        options = {"template": value} if isinstance(value, str) else value
        if not isinstance(options, dict) or "template" not in options:
            raise ConfigError(f"{label} requires a template")
        name = str(options["template"])
        timeout = float(options.get("timeout", self.config.default_timeout))
        deadline = time.monotonic() + timeout
        best: Match | None = None
        last_screen: np.ndarray | None = None
        while True:
            last_screen = self.device.screenshot()
            self.last_screen = last_screen
            found = self.matcher.find(last_screen, name)
            if found:
                LOG.info("matched %s score=%.3f at %s", name, found.score, found.center)
                self._emit(
                    "match",
                    template=name,
                    score=found.score,
                    center=list(found.center),
                    box=[found.left, found.top, found.width, found.height],
                    scale=found.scale,
                    path=label,
                )
                return found
            if time.monotonic() >= deadline:
                artifact = self._save_debug(last_screen, best, name)
                raise MatchTimeout(
                    f"Timed out waiting for '{name}' after {timeout:g}s; screenshot: {artifact}"
                )
            self.sleeper(self.config.poll_interval)

    def _tap_template(self, value: Any, label: str) -> None:
        options = {"template": value} if isinstance(value, str) else value
        if not isinstance(options, dict) or "template" not in options:
            raise ConfigError(f"{label} requires a template")
        match = self._wait_for(options, label)
        offset = options.get("offset", [0, 0])
        if not isinstance(offset, list) or len(offset) != 2:
            raise ConfigError(f"{label}.offset must be [x_fraction, y_fraction]")
        x = round(match.center[0] + float(offset[0]) * match.width)
        y = round(match.center[1] + float(offset[1]) * match.height)
        self.device.tap(x, y)
        self._emit("input", kind="tap", x=x, y=y, template=match.name, path=label)
        after = float(options.get("after", 0))
        if after > 0:
            self.sleeper(after)

    @staticmethod
    def _point(value: Any, screen: np.ndarray) -> tuple[int, int]:
        if not isinstance(value, list) or len(value) != 2:
            raise ConfigError("normalized point must be [x, y]")
        x, y = float(value[0]), float(value[1])
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ConfigError("normalized point values must be within 0..1")
        height, width = screen.shape[:2]
        return round(x * (width - 1)), round(y * (height - 1))

    def _swipe(self, value: Any, label: str) -> None:
        if not isinstance(value, dict) or "from" not in value or "to" not in value:
            raise ConfigError("swipe requires from and to normalized points")
        screen = self.device.screenshot()
        x1, y1 = self._point(value["from"], screen)
        x2, y2 = self._point(value["to"], screen)
        duration_ms = int(value.get("duration_ms", 300))
        self.device.swipe(x1, y1, x2, y2, duration_ms)
        self._emit(
            "input",
            kind="swipe",
            start=[x1, y1],
            end=[x2, y2],
            duration_ms=duration_ms,
            path=label,
        )

    def _repeat(self, value: Any, label: str) -> None:
        if not isinstance(value, dict) or not isinstance(value.get("steps"), list):
            raise ConfigError(f"{label} requires count and steps")
        count = int(value.get("count", 1))
        if not 0 <= count <= 100000:
            raise ConfigError(f"{label}.count must be within 0..100000")
        for iteration in range(count):
            self._run_steps(value["steps"], f"{label}[{iteration}].steps")

    def _save_screen(self, filename: str) -> Path:
        safe_name = Path(filename).name
        if not safe_name.lower().endswith((".png", ".jpg", ".jpeg")):
            safe_name += ".png"
        screen = self.device.screenshot()
        path = self.config.artifact_dir / safe_name
        if not cv2.imwrite(str(path), screen):
            raise ConfigError(f"Could not write screenshot: {path}")
        return path

    def _save_debug(self, screen: np.ndarray, match: Match | None, name: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        path = self.config.artifact_dir / f"timeout-{name}-{stamp}.png"
        cv2.imwrite(str(path), annotate(screen, match, name))
        return path

    def _emit(self, event_type: str, **fields: Any) -> None:
        event = {
            "type": event_type,
            "utc": datetime.now(UTC).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            **fields,
        }
        try:
            self.observer.on_event(event)
        except Exception:
            LOG.exception("run observer failed while handling %s", event_type)
