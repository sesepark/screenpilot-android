from pathlib import Path

from screenpilot.extensions import RunObserver, create_extension


def test_loads_observer_by_dotted_path(tmp_path: Path) -> None:
    destination = tmp_path / "events.jsonl"
    observer = create_extension(
        "screenpilot_user.extensions.JsonlObserver", {"path": str(destination)}
    )
    assert isinstance(observer, RunObserver)
    observer.on_event({"type": "test", "value": 3})
    assert '"type": "test"' in destination.read_text(encoding="utf-8")
