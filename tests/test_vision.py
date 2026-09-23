from pathlib import Path

import cv2
import numpy as np

from screenpilot.config import TemplateSpec
from screenpilot.vision import TemplateMatcher


def patterned_button(width: int = 100, height: int = 48) -> np.ndarray:
    image = np.zeros((height, width), dtype=np.uint8)
    cv2.rectangle(image, (2, 2), (width - 3, height - 3), 210, -1)
    cv2.rectangle(image, (8, 8), (width - 9, height - 9), 45, -1)
    cv2.circle(image, (width // 3, height // 2), 10, 245, -1)
    cv2.line(image, (width // 2, 10), (width - 14, height - 11), 170, 4)
    return image


def test_finds_scaled_template_in_normalized_roi(tmp_path: Path) -> None:
    template = patterned_button()
    template_path = tmp_path / "button.png"
    cv2.imwrite(str(template_path), template)
    scaled = cv2.resize(template, None, fx=1.25, fy=1.25, interpolation=cv2.INTER_CUBIC)
    screen = np.full((500, 900), 12, dtype=np.uint8)
    top, left = 310, 590
    screen[top : top + scaled.shape[0], left : left + scaled.shape[1]] = scaled

    spec = TemplateSpec(
        "button",
        template_path,
        threshold=0.85,
        min_scale=0.8,
        max_scale=1.5,
        scale_steps=15,
        roi=(0.5, 0.4, 1.0, 1.0),
    )
    match = TemplateMatcher({"button": spec}).find(screen, "button")

    assert match is not None
    assert match.score > 0.98
    assert abs(match.left - left) <= 1
    assert abs(match.top - top) <= 1
    assert abs(match.scale - 1.25) < 0.02


def test_returns_none_below_threshold(tmp_path: Path) -> None:
    template_path = tmp_path / "button.png"
    cv2.imwrite(str(template_path), patterned_button())
    screen = np.random.default_rng(7).integers(0, 255, (300, 500), dtype=np.uint8)
    spec = TemplateSpec("button", template_path, threshold=0.99)
    assert TemplateMatcher({"button": spec}).find(screen, "button") is None
