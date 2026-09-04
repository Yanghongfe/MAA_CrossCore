from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

import ensure_mumu


def choose(infos, requested=None, cached=None):
    with (
        patch.object(ensure_mumu, "load_json", return_value={"vm_index": cached}),
        patch.object(
            ensure_mumu,
            "manager_info",
            side_effect=lambda _manager, index: infos.get(index, {}),
        ),
    ):
        return ensure_mumu.choose_instance(
            Path("MuMuManager.exe"), requested=requested, cached_index=cached
        )[0]


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


def test_ambiguous_stopped_instances_use_lowest_index():
    infos = {
        1: {"index": 1, "disk_size_bytes": 100},
        2: {"index": 2, "disk_size_bytes": 500},
    }
    assert choose(infos) == 1


def test_offline_connection_recovers_without_server_restart():
    runner = patch.object(ensure_mumu, "run", return_value=(0, "", ""))
    with (
        runner as mocked_run,
        patch.object(ensure_mumu, "connection_usable", side_effect=[False, True]),
    ):
        assert ensure_mumu.recover_existing_adb(
            Path("adb.exe"), "127.0.0.1:16416", {}
        )
    commands = [call.args[0][1] for call in mocked_run.call_args_list]
    assert commands == ["disconnect", "connect"]


def test_other_online_device_blocks_global_adb_restart():
    with (
        patch.object(ensure_mumu, "run", return_value=(0, "", "")) as mocked_run,
        patch.object(ensure_mumu, "connection_usable", side_effect=[False, False]),
        patch.object(ensure_mumu, "adb_devices", return_value={"emulator-5554": "device"}),
    ):
        assert not ensure_mumu.recover_existing_adb(
            Path("adb.exe"), "127.0.0.1:16416", {}
        )
    assert all(call.args[0][1] != "kill-server" for call in mocked_run.call_args_list)


def test_runtime_settings_read_task_options():
    instance = {
        "TaskItems": [{
            "entry": "进入首页",
            "option": [
                {"name": "MuMu实例", "index": 3},
                {"name": "模拟器自动启动", "index": 1},
                {"name": "每次重新检测连接", "index": 1},
            ],
        }]
    }
    definitions = {
        "option": {
            "MuMu实例": {"cases": [{"name": "自动"}, {"name": "0"}, {"name": "1"}, {"name": "2"}]},
            "模拟器自动启动": {"cases": [{"name": "开启"}, {"name": "关闭"}]},
            "每次重新检测连接": {"cases": [{"name": "关闭"}, {"name": "开启"}]},
        }
    }
    with patch.dict(os.environ, {}, clear=True), patch.object(
        ensure_mumu, "interface_data", return_value=definitions
    ):
        settings = ensure_mumu.runtime_settings(instance)
    assert settings == {"vm_index": 2, "auto_start": False, "redetect": True}


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"MUMU_DISCOVERY_OK ({len(tests)} tests)")
