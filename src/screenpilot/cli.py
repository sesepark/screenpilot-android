from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2

from .adb import AdbDevice
from .config import load_config
from .errors import ScreenPilotError
from .extensions import (
    AutomationBackend,
    CompositeObserver,
    NullObserver,
    RunObserver,
    create_extension,
)
from .runner import WorkflowRunner


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="screenpilot", description="Screen-only Android automation")
    root.add_argument("--verbose", action="store_true", help="show detailed logs")
    commands = root.add_subparsers(dest="command", required=True)
    devices = commands.add_parser("devices", help="list ADB devices and emulators")
    devices.add_argument("--adb", default="adb", help="ADB executable path")
    validate = commands.add_parser("validate", help="validate a workflow and its assets")
    validate.add_argument("workflow")
    run = commands.add_parser("run", help="run a workflow")
    run.add_argument("workflow")
    run.add_argument("--serial", help="override settings.serial")
    capture = commands.add_parser(
        "capture", help="save one emulator screenshot as a template source"
    )
    capture.add_argument("output")
    capture.add_argument("--serial")
    capture.add_argument("--adb", default="adb")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        if args.command == "devices":
            devices = AdbDevice.list_devices(args.adb)
            if not devices:
                print("No ADB devices found")
            for item in devices:
                print(f"{item.serial}\t{item.state}\t{item.description}")
            return 0
        if args.command == "validate":
            config = load_config(args.workflow)
            print(f"OK: {len(config.templates)} templates, {len(config.steps)} top-level steps")
            return 0
        if args.command == "capture":
            device = AdbDevice(args.serial, args.adb)
            destination = Path(args.output).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(destination), device.screenshot()):
                raise ScreenPilotError(f"Could not write {destination}")
            print(destination)
            return 0
        if args.command == "run":
            config = load_config(args.workflow)
            if config.backend:
                if args.serial:
                    raise ScreenPilotError("--serial cannot be combined with a custom backend")
                device = create_extension(config.backend.class_path, config.backend.options)
                if not isinstance(device, AutomationBackend):
                    raise ScreenPilotError(
                        "Custom backend does not implement AutomationBackend: "
                        f"{config.backend.class_path}"
                    )
            else:
                device = AdbDevice(args.serial or config.serial, config.adb_path)

            observers: list[RunObserver] = []
            for spec in config.observers:
                observer = create_extension(spec.class_path, spec.options)
                if not isinstance(observer, RunObserver):
                    raise ScreenPilotError(
                        f"Custom observer does not implement RunObserver: {spec.class_path}"
                    )
                observers.append(observer)
            combined_observer = CompositeObserver(observers) if observers else NullObserver()
            WorkflowRunner(config, device, observer=combined_observer).run()
            print("Workflow completed")
            return 0
    except KeyboardInterrupt:
        print("Stopped", file=sys.stderr)
        return 130
    except ScreenPilotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
