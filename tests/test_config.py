from pathlib import Path

import cv2
import numpy as np
import pytest

from screenpilot.config import load_config
from screenpilot.errors import ConfigError


def test_loads_paths_relative_to_workflow(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    cv2.imwrite(str(images / "go.png"), np.zeros((10, 10), dtype=np.uint8))
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text(
        """
settings:
  artifact_dir: output
templates:
  go:
    path: images/go.png
    roi: [0.1, 0.2, 0.9, 0.8]
steps:
  - tap: go
""",
        encoding="utf-8",
    )
    config = load_config(workflow)
    assert config.templates["go"].path == images / "go.png"
    assert config.artifact_dir == tmp_path / "output"


def test_rejects_invalid_roi(tmp_path: Path) -> None:
    image = tmp_path / "go.png"
    cv2.imwrite(str(image), np.zeros((10, 10), dtype=np.uint8))
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text(
        "templates:\n  go:\n    path: go.png\n    roi: [0, 0, 2, 1]\nsteps:\n  - tap: go\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="normalized rectangle"):
        load_config(workflow)
