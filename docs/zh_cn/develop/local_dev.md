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

打开 LAA 本体时不会连接或启动模拟器。勾选“启动游戏”并点击“开始任务”后，`agent/ensure_mumu.py` 会依次完成：

1. 查找 MuMu 12 安装目录。
2. 选择已启动的实例；没有运行实例时选择主实例或数据量最大的有效实例。
3. 调用 `MuMuManager.exe` 启动实例并等待 Android 就绪。
4. 从实例信息读取实际 ADB 地址和端口，连接设备并写入当前 MFA 配置。
5. 根据资源选择启动官服或 B 服游戏。

定位顺序包括环境变量、上次成功缓存、Windows 卸载注册表，以及各磁盘常见安装目录。程序不会递归扫描整块磁盘。

多开环境选择不正确时，可设置以下环境变量后重新启动 LAA：

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
| `agent/` | 竞技场、芯片筛选、导航及 MuMu 启动逻辑 |
| `ui_custom/MFAAvalonia/` | LAA 使用的 MFAAvalonia 可复现补丁 |

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
| MuMu 已启动但 ADB 失败 | 在多开器中确认 Android 已完全启动，并检查防火墙或被占用端口 |
| 提示游戏包不存在 | 确认所选资源与实例中安装的官服/B 服一致 |
| 双击源码中的文件无法运行 | 使用完整 Release 包，或先按 `tools/install.py` 流程组装运行目录 |
| OCR 模型加载失败 | 确认完整包中有 `resource/model/ocr/` 下的模型文件 |

日志默认位于程序目录的 `debug/`。排错时优先查看最新日志中的 `[MuMu pretask]`、ADB 和 Agent 启动记录。

## 参考

- [MaaFramework 快速开始](https://maafw.com/docs/1.1-QuickStarted)
- [ProjectInterface V2](https://maafw.com/docs/3.3-ProjectInterfaceV2)
- [如何开发](./how_to_develop.md)
- [个性化配置](./custom_configure.md)
