"""Run a non-destructive chip scan against a connected MuMu instance."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install"
os.environ.setdefault("MAAFW_BINARY_PATH", str(INSTALL / "runtimes" / "win-x64" / "native"))
os.environ.setdefault("LAA_CHIP_FILTER_PREVIEW", "1")
os.environ.setdefault("LAA_CHIP_FILTER_DRY_RUN", "1")
os.environ.setdefault("TEMP", str(ROOT / ".tmp" / "preview"))
os.environ.setdefault("TMP", os.environ["TEMP"])
sys.path.insert(0, str(ROOT / "agent"))

from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker

from chip_filter_flow import ChipFilterFlow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=19)
    parser.add_argument("--adb", default=r"E:\MuMuPlayer-12.0\shell\adb.exe")
    parser.add_argument("--address", default="127.0.0.1:16416")
    args = parser.parse_args()

    os.environ["LAA_CHIP_FILTER_SCAN_LIMIT"] = str(max(1, args.limit))
    temp_dir = Path(os.environ["TEMP"])
    temp_dir.mkdir(parents=True, exist_ok=True)
    Tasker.set_log_dir(temp_dir / "maa-log")

    resource = Resource()
    if not resource.post_bundle(INSTALL / "resource").wait().succeeded:
        raise RuntimeError("Failed to load Maa resource bundle")
    if not resource.register_custom_action("chip_filter_flow", ChipFilterFlow()):
        raise RuntimeError("Failed to register chip filter action")

    controller = AdbController(
        args.adb,
        args.address,
        agent_path=INSTALL / "libs" / "MaaAgentBinary",
    )
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("Failed to connect MuMu ADB controller")

    tasker = Tasker()
    if not tasker.bind(resource, controller) or not tasker.inited:
        raise RuntimeError("Failed to initialize Maa tasker")
    job = tasker.post_task("ChipDetailReadTask").wait()
    print("CHIP_PREVIEW_STATUS", job.status)
    return 0 if job.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
