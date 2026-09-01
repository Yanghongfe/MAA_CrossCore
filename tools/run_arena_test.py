"""Run the production arena Pipeline directly for focused integration testing."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install"
os.environ.setdefault("MAAFW_BINARY_PATH", str(INSTALL / "runtimes" / "win-x64" / "native"))
os.environ.setdefault("TEMP", str(ROOT / ".tmp" / "arena-test"))
os.environ.setdefault("TMP", os.environ["TEMP"])
sys.path.insert(0, str(ROOT / "agent"))

from maa.controller import AdbController
from maa.context import ContextEventSink
from maa.resource import Resource
from maa.tasker import Tasker

from arena_pipeline import ArenaPipelineAction, ArenaPipelineRecognition


class DiagnosticSink(ContextEventSink):
    def on_raw_notification(self, context, msg, details):
        if msg == "Node.PipelineNode.Failed":
            name = details.get("name") or details.get("entry") or ""
            print(f"MAA_EVENT {msg} {name}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", default=r"E:\MuMuPlayer-12.0\shell\adb.exe")
    parser.add_argument("--address", default="127.0.0.1:16416")
    parser.add_argument("--strategy", default="尽量完成挑战")
    parser.add_argument("--repeat", default="自定次数")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--power-gap", type=int, default=5000)
    args = parser.parse_args()
    os.environ["ARENA_STRATEGY"] = args.strategy
    os.environ["ARENA_REPEAT"] = args.repeat
    os.environ["ARENA_COUNT"] = str(max(1, args.count))
    os.environ["ARENA_POWER_GAP"] = str(max(0, args.power_gap))
    os.environ.setdefault(
        "MAA_INSTANCE_CONFIG", str(INSTALL / "config" / "instances" / "default.json")
    )
    temp_dir = Path(os.environ["TEMP"])
    temp_dir.mkdir(parents=True, exist_ok=True)
    Tasker.set_log_dir(temp_dir / "maa-log")

    resource = Resource()
    if not resource.post_bundle(INSTALL / "resource").wait().succeeded:
        raise RuntimeError("Failed to load Maa resource bundle")
    if not resource.register_custom_action("arena_atomic", ArenaPipelineAction()):
        raise RuntimeError("Failed to register arena atomic action")
    if not resource.register_custom_recognition("arena_state", ArenaPipelineRecognition()):
        raise RuntimeError("Failed to register arena state recognition")

    controller = AdbController(args.adb, args.address, agent_path=INSTALL / "libs" / "MaaAgentBinary")
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("Failed to connect MuMu ADB controller")
    tasker = Tasker()
    if not tasker.bind(resource, controller) or not tasker.inited:
        raise RuntimeError("Failed to initialize Maa tasker")
    tasker.add_context_sink(DiagnosticSink())
    job = tasker.post_task("ArenaTask").wait()
    print(
        "ARENA_TEST_STATUS",
        f"succeeded={job.succeeded}",
        f"failed={job.status.failed}",
        f"raw={job.status._status.name}",
    )
    return 0 if job.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
