from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

import ensure_mumu


def choose(infos, requested=None, cached=None):
    env = {} if requested is None else {"MUMU_VM_INDEX": str(requested)}
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(ensure_mumu, "load_json", return_value={"vm_index": cached}),
        patch.object(
            ensure_mumu,
            "manager_info",
            side_effect=lambda _manager, index: infos.get(index, {}),
        ),
    ):
        return ensure_mumu.choose_instance(Path("MuMuManager.exe"))[0]


def test_running_android_wins():
    infos = {
        0: {"index": 0, "is_main": True, "disk_size_bytes": 100},
        2: {"index": 2, "is_android_started": True, "disk_size_bytes": 10},
    }
    assert choose(infos) == 2


def test_requested_running_instance_wins_between_running_instances():
    infos = {
        1: {"index": 1, "is_android_started": True},
        3: {"index": 3, "is_android_started": True},
    }
    assert choose(infos, requested=3) == 3


def test_cached_running_instance_wins_between_running_instances():
    infos = {
        1: {"index": 1, "is_android_started": True},
        4: {"index": 4, "is_android_started": True},
    }
    assert choose(infos, cached=4) == 4


def test_main_instance_wins_when_all_stopped():
    infos = {
        0: {"index": 0, "is_main": True, "disk_size_bytes": 10},
        1: {"index": 1, "disk_size_bytes": 1000},
    }
    assert choose(infos) == 0


def test_largest_instance_is_last_fallback():
    infos = {
        1: {"index": 1, "disk_size_bytes": 100},
        2: {"index": 2, "disk_size_bytes": 500},
    }
    assert choose(infos) == 2


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"MUMU_DISCOVERY_OK ({len(tests)} tests)")
