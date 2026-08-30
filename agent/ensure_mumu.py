"""MFA pretask: discover MuMu 12, start it, configure ADB, and launch the game."""

from __future__ import annotations

import json
import os
from pathlib import Path
import string
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_ROOT / "config" / "mumu_runtime.json"
START_ENTRIES = {"进入首页", "StartGameTask"}
PACKAGES = {
    "B 服": "com.megagame.crosscore.bilibili",
    "B服": "com.megagame.crosscore.bilibili",
}
DEFAULT_PACKAGE = "com.megagame.crosscore"
INSTANCE_OPTION = "MuMu实例"
AUTOSTART_OPTION = "模拟器自动启动"
REDETECT_OPTION = "每次重新检测连接"


def log(message):
    print(f"[MuMu pretask] {message}", flush=True)


def run(args, timeout=30):
    try:
        result = subprocess.run(
            [str(value) for value in args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {} if default is None else default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.2)


def instance_files():
    directory = PROJECT_ROOT / "config" / "instances"
    return sorted(directory.glob("*.json")) if directory.exists() else []


def selected_instance():
    fallback = None
    for path in instance_files():
        data = load_json(path)
        fallback = fallback or (path, data)
        for task in data.get("TaskItems", []):
            if task.get("entry") in START_ENTRIES and task.get("default_check", False):
                return path, data
    return fallback or (None, {})


def start_game_selected(instance):
    return any(
        task.get("entry") in START_ENTRIES and task.get("default_check", False)
        for task in instance.get("TaskItems", [])
    )


def start_task(instance):
    return next(
        (task for task in instance.get("TaskItems", []) if task.get("entry") in START_ENTRIES),
        {},
    )


def interface_data():
    for path in (PROJECT_ROOT / "interface.json", PROJECT_ROOT / "assets" / "interface.json"):
        if path.is_file():
            return load_json(path)
    return {}


def task_option_case(instance, option_name, default):
    selected = next(
        (option for option in start_task(instance).get("option", []) if option.get("name") == option_name),
        None,
    )
    definition = interface_data().get("option", {}).get(option_name, {})
    cases = definition.get("cases", [])
    if selected is None:
        return str(definition.get("default_case", default))
    index = selected.get("index", 0)
    if isinstance(index, int) and 0 <= index < len(cases):
        return str(cases[index].get("name", default))
    return default


def runtime_settings(instance):
    configured_index = task_option_case(instance, INSTANCE_OPTION, "自动")
    env_index = os.environ.get("MUMU_VM_INDEX")
    requested_index = env_index if env_index is not None else configured_index
    requested_index = int(requested_index) if str(requested_index).isdigit() else None
    return {
        "vm_index": requested_index,
        "auto_start": task_option_case(instance, AUTOSTART_OPTION, "开启") != "关闭",
        "redetect": task_option_case(instance, REDETECT_OPTION, "关闭") == "开启",
    }


def registry_locations():
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    locations = []
    roots = (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, key_name in roots:
        try:
            with winreg.OpenKey(hive, key_name) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, index)) as item:
                            name = str(winreg.QueryValueEx(item, "DisplayName")[0])
                            if "mumu" not in name.lower() and "网易模拟器" not in name:
                                continue
                            for value_name in ("InstallLocation", "DisplayIcon", "UninstallString"):
                                try:
                                    value = str(winreg.QueryValueEx(item, value_name)[0]).strip(' "')
                                    locations.append(Path(value).parent if value.lower().endswith(".exe") else Path(value))
                                except OSError:
                                    pass
                    except OSError:
                        pass
        except OSError:
            pass
    return locations


def candidate_roots():
    cached = load_json(CACHE_FILE)
    values = [
        os.environ.get("MUMU_HOME"),
        cached.get("root"),
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    values.extend(registry_locations())
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:\\")
        if drive.exists():
            values.extend((
                drive / "MuMuPlayer-12.0",
                drive / "Netease" / "MuMuPlayer-12.0",
                drive / "Program Files" / "Netease" / "MuMuPlayer-12.0",
                drive / "Program Files (x86)" / "Netease" / "MuMuPlayer-12.0",
            ))
    seen = set()
    for value in values:
        if not value:
            continue
        path = Path(value).expanduser()
        variants = (path, path / "Netease" / "MuMuPlayer-12.0", path / "MuMuPlayer-12.0")
        for candidate in variants:
            key = str(candidate).lower()
            if key not in seen:
                seen.add(key)
                yield candidate


def find_mumu():
    explicit_manager = os.environ.get("MUMU_MANAGER")
    if explicit_manager and Path(explicit_manager).is_file():
        manager = Path(explicit_manager)
        root = manager.parent.parent
        return root, manager, find_adb(root)
    for root in candidate_roots():
        manager = root / "nx_main" / "MuMuManager.exe"
        if manager.is_file():
            adb = find_adb(root)
            if adb:
                return root.resolve(), manager.resolve(), adb.resolve()
    return None, None, None


def find_adb(root):
    explicit = os.environ.get("MUMU_ADB")
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    for relative in (Path("shell/adb.exe"), Path("nx_main/adb.exe"), Path("adb.exe")):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def manager_info(manager, index):
    code, output, _ = run([manager, "info", "--vmindex", index], timeout=12)
    if code or not output:
        return {}
    try:
        info = json.loads(output)
        return info if info.get("error_code", 0) == 0 and "index" in info else {}
    except json.JSONDecodeError:
        return {}


def choose_instance(manager, requested=None, preferred_serial="", use_cache=True):
    cached_index = load_json(CACHE_FILE).get("vm_index") if use_cache else None
    requested = requested if requested is not None else cached_index
    indexes = []
    if requested is not None and str(requested).isdigit():
        indexes.append(int(requested))
    indexes.extend(index for index in range(10) if index not in indexes)
    found = [(index, manager_info(manager, index)) for index in indexes]
    found = [(index, info) for index, info in found if info]
    if not found:
        return None, {}
    if requested is not None:
        return found[0]

    def unique(candidates):
        if len(candidates) == 1:
            return candidates[0]
        if preferred_serial:
            for candidate in candidates:
                info = candidate[1]
                serial = f"{info.get('adb_host_ip') or '127.0.0.1'}:{info.get('adb_port')}"
                if serial == preferred_serial:
                    return candidate
        return None

    running = [item for item in found if item[1].get("is_android_started")]
    if choice := unique(running):
        return choice
    process_started = [item for item in found if item[1].get("is_process_started")]
    if choice := unique(process_started):
        return choice
    if len(found) == 1:
        return found[0]
    main_instances = [item for item in found if item[1].get("is_main")]
    if choice := unique(main_instances):
        return choice
    return None, {"candidates": [index for index, _ in found]}


def ensure_android(manager, index, info, allow_start=True):
    if not info.get("is_process_started") and not info.get("is_android_started"):
        if not allow_start:
            log(f"MuMu 实例 {index} 尚未启动，且已关闭自动启动")
            return {}
        log(f"正在启动 MuMu 12 实例 {index}")
        code, output, error = run(
            [manager, "control", "--vmindex", index, "launch"], timeout=60
        )
        if code:
            log(f"启动 MuMu 失败：{error or output}")
            return {}
    else:
        log(f"MuMu 12 实例 {index} 已在运行，等待 Android 就绪")
    for _ in range(150):
        current = manager_info(manager, index)
        if current.get("is_android_started"):
            return current
        time.sleep(1)
    log("MuMu Android 启动超时")
    return {}


def adb_devices(adb):
    _, output, _ = run([adb, "devices"], timeout=20)
    devices = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] != "List":
            devices[fields[0]] = fields[1]
    return devices


def adb_state(adb, serial):
    code, output, _ = run([adb, "-s", serial, "get-state"], timeout=12)
    return output.strip() if code == 0 else ""


def recover_existing_adb(adb, serial, allow_hard_restart=True):
    if adb_state(adb, serial) == "device":
        return True
    log(f"已保存的 ADB {serial} 不可用，尝试重新连接")
    if ":" in serial:
        run([adb, "disconnect", serial], timeout=10)
        run([adb, "connect", serial], timeout=15)
    if adb_state(adb, serial) == "device":
        return True

    devices = adb_devices(adb)
    other_online = [
        device for device, state in devices.items() if device != serial and state == "device"
    ]
    if not allow_hard_restart or other_online:
        if other_online:
            log("检测到其他在线 ADB 设备，跳过全局 ADB Server 重启")
        return False

    log("普通重连失败，重启 ADB Server 后再试一次")
    run([adb, "kill-server"], timeout=15)
    run([adb, "start-server"], timeout=20)
    if ":" in serial:
        run([adb, "connect", serial], timeout=15)
    return adb_state(adb, serial) == "device"


def saved_connection(instance):
    device = instance.get("AdbDevice", {})
    adb = Path(str(device.get("AdbPath", "")))
    serial = str(device.get("AdbSerial", "")).strip()
    if adb.is_file() and serial:
        return adb, serial
    return None


def ensure_adb(adb, info, index):
    run([adb, "start-server"], timeout=20)
    host = str(info.get("adb_host_ip") or "127.0.0.1")
    port = info.get("adb_port")
    tcp = f"{host}:{port}" if port else ""
    emulator = f"emulator-{5554 + index * 2}"
    for _ in range(50):
        devices = adb_devices(adb)
        for serial in (tcp, emulator):
            if serial and devices.get(serial) == "device":
                return serial
        if tcp:
            if devices.get(tcp) == "offline":
                run([adb, "disconnect", tcp], timeout=10)
            run([adb, "connect", tcp], timeout=15)
        time.sleep(0.5)
    return ""


def update_instance(path, instance, adb, serial, root, index):
    if not path:
        return
    device = {
        "Name": f"MuMu 12（实例 {index}）",
        "AdbPath": str(adb),
        "AdbSerial": serial,
        "ScreencapMethods": 18446744073709551559,
        "InputMethods": 4,
        "Config": json.dumps({
            "extras": {"mumu": {"enable": True, "index": index, "path": root.as_posix()}}
        }, ensure_ascii=False, separators=(",", ":")),
        "AgentPath": "./MaaAgentBinary",
    }
    if instance.get("AdbDevice") == device:
        log(f"MFA 已使用当前 ADB 连接：{serial}")
        return
    instance["AdbDevice"] = device
    save_json(path, instance)
    log(f"已写入 MFA 连接：{serial}")


def top_has_package(adb, serial, package):
    _, output, _ = run(
        [adb, "-s", serial, "shell", "dumpsys", "activity", "activities"], timeout=30
    )
    return any(
        package in line and ("topResumedActivity" in line or "mResumedActivity" in line)
        for line in output.splitlines()
    )


def launch_game(adb, serial, package):
    if top_has_package(adb, serial, package):
        log("交错战线已经位于前台")
        return True
    for _ in range(2):
        run([
            adb, "-s", serial, "shell", "monkey", "-p", package,
            "-c", "android.intent.category.LAUNCHER", "1",
        ], timeout=30)
        for _ in range(30):
            time.sleep(0.5)
            if top_has_package(adb, serial, package):
                return True
    log(f"未能启动游戏包 {package}，请确认已在该 MuMu 实例中安装")
    return False


def main():
    instance_path, instance = selected_instance()
    if not start_game_selected(instance):
        log("未选择“启动游戏”，不启动 MuMu")
        return 0
    if os.name != "nt":
        log("MuMu 12 自动启动目前仅支持 Windows")
        return 1

    settings = runtime_settings(instance)
    resource = str(instance.get("Resource", ""))
    package = PACKAGES.get(resource, DEFAULT_PACKAGE)

    saved = saved_connection(instance)
    if saved and not settings["redetect"]:
        adb, serial = saved
        log(f"[1/4] 检查已保存的 ADB 连接：{serial}")
        if recover_existing_adb(adb, serial):
            log("[2/4] 已保存的 ADB 连接可用，跳过模拟器扫描")
            log(f"[3/4] 正在启动交错战线：{package}")
            result = launch_game(adb, serial, package)
            log("[4/4] 启动游戏流程完成" if result else "[4/4] 启动游戏失败")
            return 0 if result else 1
        log("已保存连接恢复失败，转入 MuMu 检测流程")

    log("[1/4] 正在查找 MuMu 12")
    root, manager, adb = find_mumu()
    if not manager or not adb:
        log("未找到 MuMu 12；可设置 MUMU_HOME 指向安装目录后重试")
        return 1
    log(f"发现 MuMu 12：{root}")

    preferred_serial = saved[1] if saved else ""
    index, info = choose_instance(
        manager,
        requested=settings["vm_index"],
        preferred_serial=preferred_serial,
        use_cache=settings["vm_index"] is None,
    )
    if index is None:
        candidates = info.get("candidates", [])
        if candidates:
            log(f"发现多个 MuMu 实例 {candidates}，请在“启动游戏”设置中选择实例")
        else:
            log("没有发现可用的 MuMu 12 实例")
        return 1
    log(f"[2/4] 使用 MuMu 实例 {index}")
    info = ensure_android(manager, index, info, allow_start=settings["auto_start"])
    if not info:
        return 1
    serial = ensure_adb(adb, info, index)
    if not serial:
        log("MuMu 已启动，但 ADB 连接失败")
        return 1

    save_json(CACHE_FILE, {"root": str(root), "vm_index": index, "adb_serial": serial})
    update_instance(instance_path, instance, adb, serial, root, index)
    log(f"[3/4] 正在启动交错战线：{package}")
    result = launch_game(adb, serial, package)
    log("[4/4] 启动游戏流程完成" if result else "[4/4] 启动游戏失败")
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
