# 本地开发手册（MuMu 12 + MFAAvalonia）

本文说明 Windows 下运行和调试本项目的推荐方式。项目不依赖开发者电脑上的固定盘符、ADB 端口或 MuMu 实例编号。

## 运行前提

- Windows x64
- MuMu 模拟器 12，且目标实例中已安装《交错战线》
- Python 3.10 或更高版本，并安装 `maafw`、`numpy`、`opencv-python`
- 从 Release 下载完整程序包；仅下载 GitHub 源码不会包含 MFAAvalonia、MaaFramework 运行库和 OCR 模型

开发环境可在仓库根目录创建虚拟环境：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install maafw numpy opencv-python
```

## 启动游戏任务

打开 LAA 本体时不会连接或启动模拟器。勾选“启动游戏”并点击“开始任务”后，`agent/ensure_mumu.py`（pretask）会依次完成：

1. 验证上次保存的 ADB；连接健康时直接复用并跳过模拟器扫描。
2. 普通重连失败后，在没有其他在线 ADB 设备时重启 ADB Server。
3. 仍无法连接时查找 MuMu 12，并按用户设置、历史成功实例、唯一运行实例的顺序选择。
4. 调用 `MuMuManager.exe` 启动实例并等待 Android 就绪。
5. 从实例信息读取实际 ADB 地址和端口，连接设备并写入当前 MFA 配置。

pretask **不会**打开交错战线。开游戏由 pipeline「启动游戏」任务中的 `StartApp` 负责（官服 / B 服包名见 `启动游戏.json` 与 `bilibili/pipeline/startup.json`）。

定位顺序包括环境变量、上次成功缓存、Windows 卸载注册表，以及各磁盘常见安装目录。程序不会递归扫描整块磁盘。

“启动游戏”的任务设置提供以下选项：

| 选项 | 默认 | 作用 |
| --- | --- | --- |
| MuMu 实例 | 自动 | 自动模式只选择可唯一确定或历史成功的实例；多开有歧义时要求用户明确选择 0-9 |
| ADB 失败时启动模拟器 | 开启 | 关闭后只连接已经启动的实例 |
| 每次重新检测连接 | 关闭 | 开启后跳过已保存 ADB 快速路径，重新读取 MuMu 实例信息 |

多个实例无法唯一判断时，程序不会根据磁盘大小猜测。用户选择会随 MFA 配置持久保存。也可设置以下环境变量覆盖界面配置：

| 变量 | 作用 | 示例 |
| --- | --- | --- |
| `MUMU_VM_INDEX` | 指定 MuMu 实例编号 | `1` |
| `MUMU_HOME` | 指定 MuMu 12 安装根目录 | `E:\MuMuPlayer-12.0` |
| `MUMU_MANAGER` | 直接指定 `MuMuManager.exe` | `E:\MuMuPlayer-12.0\nx_main\MuMuManager.exe` |
| `MUMU_ADB` | 直接指定 MuMu 自带 `adb.exe` | `E:\MuMuPlayer-12.0\nx_main\adb.exe` |

成功结果会缓存到 `config/mumu_runtime.json`。该文件仅保存本机路径、实例号和 ADB 地址，已被 Git 忽略，不会提交到仓库。

## 日常开发

主要目录：

| 路径 | 作用 |
| --- | --- |
| `assets/interface.json` | 资源、任务、选项、Agent 和 pretask 配置 |
| `assets/resource/pipeline/` | Pipeline 识别与动作流程 |
| `assets/resource/image/` | 经过裁剪的识别模板 |
| `agent/` | 订单好友、竞技场、芯片、周本 Custom、导航及 MuMu pretask |
| `ui_custom/MFAAvalonia/` | LAA 使用的 MFAAvalonia 可复现补丁 |

### Pipeline 与 Agent 分工

- Pipeline 是任务状态机的正式来源，负责页面识别、导航、点击、分支、循环、重试、接续和结束条件。
- Agent 只提供边界清晰的原子能力，例如复杂 OCR、数值判断、配置读写和单次稳定识别。
- 新功能不得把完整页面流程写成单个 Custom Action；应由 Pipeline 组合多个原子能力。
- 正式 Pipeline JSON 直接保存 `$__mpe_code`，同组成员可在 MPE 中阅读真实运行流程。
- 竞技场、芯片筛选和第五关周本仍含历史单体 Agent，后续维护时逐步迁回 Pipeline。

Pipeline 调试可使用 MaaDebugger：

```powershell
.\.venv\Scripts\python.exe -m MaaDebugger
```

浏览器访问 `http://127.0.0.1:8011`，控制器选择 Adb，并填入 MuMu 实例信息中显示的 ADB 路径和地址。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 未找到 MuMu 12 | 设置 `MUMU_HOME`，确认目录内存在 `nx_main/MuMuManager.exe` |
| 启动了错误实例 | 设置 `MUMU_VM_INDEX`，或删除 `config/mumu_runtime.json` 后重试 |
| 日志提示发现多个实例 | 在“启动游戏”任务设置中明确选择实例编号 |
| ADB 显示 `offline` | 程序会先重连；不存在其他在线设备时才会重启 ADB Server |
| MuMu 已启动但 ADB 失败 | 在多开器中确认 Android 已完全启动，并检查防火墙或被占用端口 |
| 提示游戏包不存在 / 官服起不来 | 确认 MFA 所选资源与 MuMu 实例中安装的官服/B 服一致；官服包名看 `pipeline/base/启动游戏.json`，B 服看 `bilibili/pipeline/startup.json`。pretask 不会开游戏 |
| 双击源码中的文件无法运行 | 使用完整 Release 包，或先按 `tools/install.py` 流程组装运行目录 |
| OCR 模型加载失败 | 确认完整包中有 `resource/model/ocr/` 下的模型文件 |
| Agent / Custom 无响应 | 先跑 `Install-Agent-Deps.bat`（或 `pip install -r agent/requirements.txt`），并确认 `python`/`py` 在 PATH |

日志默认位于程序目录的 `debug/`。排错时优先查看最新日志中的 `[MuMu pretask]`、ADB 和 Agent 启动记录。

## 参考

- [MaaFramework 快速开始](https://maafw.com/docs/1.1-QuickStarted)
- [ProjectInterface V2](https://maafw.com/docs/3.3-ProjectInterfaceV2)
- [如何开发](./how_to_develop.md)
- [个性化配置](./custom_configure.md)
