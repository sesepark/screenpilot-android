from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    path: Path
    threshold: float = 0.88
    min_scale: float = 0.75
    max_scale: float = 1.35
    scale_steps: int = 13
    roi: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class ExtensionSpec:
    class_path: str
    options: dict[str, Any]


@dataclass(frozen=True)
class WorkflowConfig:
    source: Path
    serial: str | None
    adb_path: str
    poll_interval: float
    default_timeout: float
    artifact_dir: Path
    templates: dict[str, TemplateSpec]
    steps: list[dict[str, Any]]
    backend: ExtensionSpec | None = None
    observers: tuple[ExtensionSpec, ...] = ()


def _normalized_rect(value: Any, label: str) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise ConfigError(f"{label} must be [left, top, right, bottom]")
    rect = tuple(float(v) for v in value)
    if not (0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1):
        raise ConfigError(f"{label} values must form a normalized rectangle within 0..1")
    return rect


def _extension_spec(value: Any, label: str) -> ExtensionSpec | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("class"), str):
        raise ConfigError(f"{label} must contain a dotted Python class path in 'class'")
    options = value.get("options", {})
    if not isinstance(options, dict):
        raise ConfigError(f"{label}.options must be a mapping")
    return ExtensionSpec(value["class"], dict(options))


def load_config(path: str | Path) -> WorkflowConfig:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigError(f"Workflow file does not exist: {source}")
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not read YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("Workflow root must be a mapping")

    settings = raw.get("settings", {})
    if not isinstance(settings, dict):
        raise ConfigError("settings must be a mapping")
    template_values = raw.get("templates", {})
    if not isinstance(template_values, dict) or not template_values:
        raise ConfigError("templates must be a non-empty mapping")

    templates: dict[str, TemplateSpec] = {}
    for name, value in template_values.items():
        if not isinstance(value, dict) or "path" not in value:
            raise ConfigError(f"templates.{name} must contain path")
        scales = value.get("scales", [0.75, 1.35, 13])
        if not isinstance(scales, list) or len(scales) != 3:
            raise ConfigError(f"templates.{name}.scales must be [min, max, steps]")
        threshold = float(value.get("threshold", 0.88))
        if not 0 < threshold <= 1:
            raise ConfigError(f"templates.{name}.threshold must be within (0, 1]")
        template_path = (source.parent / str(value["path"])).resolve()
        if not template_path.is_file():
            raise ConfigError(f"Template does not exist: {template_path}")
        templates[str(name)] = TemplateSpec(
            name=str(name),
            path=template_path,
            threshold=threshold,
            min_scale=float(scales[0]),
            max_scale=float(scales[1]),
            scale_steps=int(scales[2]),
            roi=_normalized_rect(value.get("roi"), f"templates.{name}.roi"),
        )

    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ConfigError("steps must be a non-empty list")
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or len(step) != 1:
            raise ConfigError(f"steps[{index}] must contain exactly one action")

    artifact_value = Path(str(settings.get("artifact_dir", "artifacts"))).expanduser()
    artifact_dir = (
        artifact_value if artifact_value.is_absolute() else source.parent / artifact_value
    )
    backend = _extension_spec(settings.get("backend"), "settings.backend")
    observer_values = settings.get("observers", [])
    if not isinstance(observer_values, list):
        raise ConfigError("settings.observers must be a list")
    observers = tuple(
        spec
        for index, value in enumerate(observer_values)
        if (spec := _extension_spec(value, f"settings.observers[{index}]")) is not None
    )
    return WorkflowConfig(
        source=source,
        serial=str(settings["serial"]) if settings.get("serial") else None,
        adb_path=str(settings.get("adb_path", "adb")),
        poll_interval=float(settings.get("poll_interval", 0.25)),
        default_timeout=float(settings.get("default_timeout", 10)),
        artifact_dir=artifact_dir.resolve(),
        templates=templates,
        steps=steps,
        backend=backend,
        observers=observers,
    )
