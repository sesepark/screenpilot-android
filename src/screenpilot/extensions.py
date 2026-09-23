"""Stable interfaces for trusted, out-of-tree extensions."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import numpy as np

from .errors import ConfigError


@runtime_checkable
class AutomationBackend(Protocol):
    """Provides screen frames and sends input to one automation target."""

    def screenshot(self) -> np.ndarray: ...

    def tap(self, x: int, y: int) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None: ...

    def keyevent(self, keycode: str) -> None: ...


@runtime_checkable
class RunObserver(Protocol):
    """Receives event copies for logging, metrics, and test correlation."""

    def on_event(self, event: Mapping[str, Any]) -> None: ...


class NullObserver:
    def on_event(self, event: Mapping[str, Any]) -> None:
        del event


class CompositeObserver:
    def __init__(self, observers: list[RunObserver]):
        self.observers = observers

    def on_event(self, event: Mapping[str, Any]) -> None:
        for observer in self.observers:
            observer.on_event(dict(event))


def load_object(class_path: str) -> type[Any]:
    """Load a class from a `package.module.ClassName` path."""
    module_name, separator, attribute = class_path.rpartition(".")
    if not separator or not module_name or not attribute:
        raise ConfigError(f"Extension class must be a dotted path: {class_path}")
    try:
        module = importlib.import_module(module_name)
    except (ImportError, ValueError) as exc:
        raise ConfigError(f"Could not import extension module '{module_name}': {exc}") from exc
    try:
        value = getattr(module, attribute)
    except AttributeError as exc:
        raise ConfigError(f"Extension class was not found: {class_path}") from exc
    if not isinstance(value, type):
        raise ConfigError(f"Extension target is not a class: {class_path}")
    return value


def create_extension(class_path: str, options: Mapping[str, Any] | None = None) -> Any:
    extension_type = load_object(class_path)
    try:
        return extension_type(**dict(options or {}))
    except TypeError as exc:
        raise ConfigError(f"Could not construct extension '{class_path}': {exc}") from exc
