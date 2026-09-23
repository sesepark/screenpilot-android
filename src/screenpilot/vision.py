from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import TemplateSpec
from .errors import ConfigError


@dataclass(frozen=True)
class Match:
    name: str
    score: float
    left: int
    top: int
    width: int
    height: int
    scale: float

    @property
    def center(self) -> tuple[int, int]:
        return self.left + self.width // 2, self.top + self.height // 2


class TemplateMatcher:
    def __init__(self, specs: dict[str, TemplateSpec]):
        self.specs = specs
        self.images: dict[str, np.ndarray] = {}
        for name, spec in specs.items():
            image = cv2.imread(str(spec.path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ConfigError(f"Could not decode template image: {spec.path}")
            self.images[name] = image

    def find(self, screen: np.ndarray, name: str) -> Match | None:
        if name not in self.specs:
            raise ConfigError(f"Unknown template: {name}")
        spec = self.specs[name]
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if screen.ndim == 3 else screen
        screen_h, screen_w = gray.shape[:2]
        x0, y0, x1, y1 = 0, 0, screen_w, screen_h
        if spec.roi:
            x0, y0 = round(spec.roi[0] * screen_w), round(spec.roi[1] * screen_h)
            x1, y1 = round(spec.roi[2] * screen_w), round(spec.roi[3] * screen_h)
        search = gray[y0:y1, x0:x1]
        best: Match | None = None
        scales = np.linspace(spec.min_scale, spec.max_scale, spec.scale_steps)
        original = self.images[name]
        for scale_value in scales:
            scale = float(scale_value)
            width = max(1, round(original.shape[1] * scale))
            height = max(1, round(original.shape[0] * scale))
            if width > search.shape[1] or height > search.shape[0] or width < 3 or height < 3:
                continue
            interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
            template = cv2.resize(original, (width, height), interpolation=interpolation)
            result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(result)
            candidate = Match(
                name, float(score), location[0] + x0, location[1] + y0, width, height, scale
            )
            if best is None or candidate.score > best.score:
                best = candidate
        return best if best and best.score >= spec.threshold else None


def annotate(screen: np.ndarray, match: Match | None, label: str) -> np.ndarray:
    output = screen.copy()
    if match:
        cv2.rectangle(
            output,
            (match.left, match.top),
            (match.left + match.width, match.top + match.height),
            (0, 255, 0),
            2,
        )
        text = f"{label} {match.score:.3f} scale={match.scale:.2f}"
        cv2.putText(
            output,
            text,
            (match.left, max(20, match.top - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
        )
    else:
        cv2.putText(
            output, f"not found: {label}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
        )
    return output
