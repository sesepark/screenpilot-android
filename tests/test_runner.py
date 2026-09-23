from pathlib import Path

import cv2
import numpy as np

from screenpilot.config import TemplateSpec, WorkflowConfig
from screenpilot.runner import WorkflowRunner


class FakeDevice:
    def __init__(self, screen: np.ndarray):
        self.screen = screen
        self.events: list[tuple] = []

    def screenshot(self) -> np.ndarray:
        return self.screen.copy()

    def tap(self, x: int, y: int) -> None:
        self.events.append(("tap", x, y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self.events.append(("swipe", x1, y1, x2, y2, duration_ms))

    def keyevent(self, keycode: str) -> None:
        self.events.append(("keyevent", keycode))


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def on_event(self, event) -> None:
        self.events.append(dict(event))


def test_workflow_uses_match_center_and_normalized_coordinates(tmp_path: Path) -> None:
    template = np.zeros((40, 80), dtype=np.uint8)
    cv2.rectangle(template, (2, 2), (77, 37), 190, -1)
    cv2.circle(template, (23, 20), 9, 255, -1)
    cv2.line(template, (42, 8), (67, 32), 45, 5)
    path = tmp_path / "target.png"
    cv2.imwrite(str(path), template)
    screen = np.full((400, 800, 3), 15, dtype=np.uint8)
    screen[200:240, 500:580] = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
    config = WorkflowConfig(
        source=tmp_path / "workflow.yaml",
        serial=None,
        adb_path="adb",
        poll_interval=0,
        default_timeout=1,
        artifact_dir=tmp_path / "artifacts",
        templates={
            "target": TemplateSpec(
                "target", path, threshold=0.95, min_scale=1, max_scale=1, scale_steps=1
            )
        },
        steps=[
            {"tap": {"template": "target"}},
            {"tap_at": [0.25, 0.75]},
            {"swipe": {"from": [0.1, 0.2], "to": [0.9, 0.8], "duration_ms": 250}},
            {"keyevent": "BACK"},
        ],
    )
    device = FakeDevice(screen)

    observer = RecordingObserver()
    WorkflowRunner(config, device, observer=observer, sleeper=lambda _: None).run()

    assert device.events == [
        ("tap", 540, 220),
        ("tap", 200, 299),
        ("swipe", 80, 80, 719, 319, 250),
        ("keyevent", "BACK"),
    ]
    assert observer.events[0]["type"] == "run_start"
    assert observer.events[-1]["type"] == "run_complete"
    assert any(event["type"] == "match" for event in observer.events)
    assert sum(event["type"] == "input" for event in observer.events) == 4


def test_repeat_runs_nested_steps(tmp_path: Path) -> None:
    template = np.arange(400, dtype=np.uint8).reshape(20, 20)
    path = tmp_path / "unused.png"
    cv2.imwrite(str(path), template)
    screen = np.zeros((100, 200, 3), dtype=np.uint8)
    config = WorkflowConfig(
        tmp_path / "workflow.yaml",
        None,
        "adb",
        0,
        1,
        tmp_path / "artifacts",
        {"unused": TemplateSpec("unused", path)},
        [{"repeat": {"count": 3, "steps": [{"tap_at": [0.5, 0.5]}]}}],
    )
    device = FakeDevice(screen)
    WorkflowRunner(config, device, sleeper=lambda _: None).run()
    assert device.events == [("tap", 100, 50)] * 3
