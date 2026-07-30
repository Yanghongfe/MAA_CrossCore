# 本地开发手册（MuMu + MaaDebugger）

面向本机日常开发：用 MuMu 模拟器 + ADB + MaaDebugger 调试 pipeline。  
官方模板流程见 [如何开发](./how_to_develop.md)；框架概念见 [快速开始](https://maafw.com/docs/1.1-QuickStarted)。

## 环境约定

| 项 | 本机路径 / 值 |
| --- | --- |
| 项目根目录 | `C:\Users\thomas\Desktop\workwork\MAA\MAA_Practice` |
| MuMu ADB | `D:\Program Files\Netease\MuMu\nx_main\adb.exe` |
| ADB 地址 | `127.0.0.1:16384`（以多开器里显示为准） |
| OCR 模型 | `assets/resource/model/ocr/`（`det.onnx` / `rec.onnx` / `keys.txt`） |
| 调试器 | http://localhost:8011 |
| 框架日志 | `debug/maafw.log` |

OCR 已在 `.gitignore` 中忽略，不要提交进仓库。

## 每次开工

1. 打开 MuMu，确认实例已启动。
2. （可选）确认 ADB：

   ```powershell
   & "D:\Program Files\Netease\MuMu\nx_main\adb.exe" connect 127.0.0.1:16384
   & "D:\Program Files\Netease\MuMu\nx_main\adb.exe" devices
   ```

   应看到 `127.0.0.1:16384    device`。

3. 在项目根目录启动调试器：

   ```powershell
   cd C:\Users\thomas\Desktop\workwork\MAA\MAA_Practice
   python -m MaaDebugger
   ```

4. 浏览器打开 http://localhost:8011 。

系统找不到 `adb` 命令是正常的：PATH 里没有它，请用上面的完整路径。

## MaaDebugger 连接（重要）

### 推荐填法

| 字段 | 值 |
| --- | --- |
| 控制器 | Adb |
| ADB 路径 | `D:\Program Files\Netease\MuMu\nx_main\adb.exe` |
| 地址 | `127.0.0.1:16384` |
| Extras / Config | `{}` |

然后点 **连接**。

### 成功怎么判断

- 前端出现 MuMu 画面 → **已连接成功**。
- 调试器成功时**几乎不往终端打「连接成功」**；失败才会红字报错。
- 连接按钮旁状态为 Succeeded / 绿色亦可作参考。

### 不要这样做

1. **地址末尾不要有空格**  
   错误示例：`127.0.0.1:16384 `（日志里会变成 `"127.0.0.1:16384 "`，直接连失败）。

2. **开发初期不要依赖「扫描设备」带出的 MuMu extras**  
   扫描常会自动填入类似：

   ```json
   {
     "extras": {
       "mumu": {
         "enable": true,
         "index": 0,
         "path": "D:/Program Files/Netease/MuMu"
       }
     }
   }
   ```

   本机上该增强通道会刷：

   ```text
   nemu_connect ...
   connect not same day
   ```

   普通 ADB 已够用。若被扫描覆盖，把 Config 改回 `{}` 再连。

3. **不要用 Win32 去「启动」MuMu**  
   本项目控制的是模拟器里的安卓画面（ADB），不是自动打开桌面端 MuMu 进程。MuMu 需先手动开着。

## 资源与任务开发

### 主要改这些文件

| 路径 | 作用 |
| --- | --- |
| `assets/interface.json` | 项目名、控制器、资源、任务列表（通用 UI / 调试入口） |
| `assets/resource/pipeline/*.json` | 任务流水线：识别 + 动作 |
| `assets/resource/image/` | 模板图 |
| `agent/` | 可选：自定义识别 / 动作（Python） |

### 调试器里加载资源

连接成功后，资源目录选：

- `assets`，或
- `assets/resource`

以工具提示为准。改 pipeline 后按工具说明重载再跑。

### 最小可跑任务示例

编辑 `assets/resource/pipeline/my_task.json`，例如：

```json
{
  "MyTask1": {
    "recognition": "OCR",
    "expected": "开始",
    "action": "Click"
  }
}
```

在 `interface.json` 中对应入口为 `MyTask1`（「普通任务」）。  
屏幕上真实存在该文字后再跑；没有就改成你画面上的字。

可视化编辑可参考 [MaaPipelineEditor](https://mpe.codax.site/stable/)。  
协议详见 [任务流水线](https://maafw.com/docs/3.1-PipelineProtocol)。

### 自定义 Agent（可选）

需要复杂逻辑时：

1. 取消 `assets/interface.json` 里 `agent` 段注释，并按本机改 `child_exec` / `child_args`。
2. 在 `agent/` 实现自定义 recognition / action。
3. pipeline 节点使用 `"recognition": "Custom"` / `"action": "Custom"`。

## 日常开发节奏

```text
开 MuMu → 启 MaaDebugger → ADB 连接（config 用 {}）
    → 加载 assets → 改 pipeline / 截图抠图
    → 跑任务验证 → 提交代码
```

发版、打 tag、CI 打包仍按 [如何开发](./how_to_develop.md) 后半部分操作。

## 排错速查

| 现象 | 处理 |
| --- | --- |
| `adb` 不是内部或外部命令 | 用 MuMu 自带完整路径，或临时：`$env:Path += ";D:\Program Files\Netease\MuMu\nx_main"` |
| `Failed to connect ... adb.exe 127.0.0.1:16384` | 查地址空格；MuMu 是否在跑；`adb devices` 是否为 `device` |
| 终端刷 `connect not same day` | Config 改为 `{}`，勿用 MuMu extras |
| 缺运行库弹窗 | 安装 [vc_redist](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| OCR 无结果 / Failed to load det or rec | 确认 `assets/resource/model/ocr/` 三文件齐全 |
| 前端有画面但终端无成功日志 | 正常；以截图为准 |

详细通用 FAQ：[faq.md](./faq.md)。

## 推荐工具

- [MaaDebugger](https://github.com/MaaXYZ/MaaDebugger)：本手册主调试方式
- VS Code / Cursor 插件 [Maa Pipeline Support](https://marketplace.visualstudio.com/items?itemName=nekosu.maa-support)
- [MaaPipelineEditor](https://mpe.codax.site/stable/)：可视化编 pipeline

## 参考链接

- [MaaFramework 快速开始](https://maafw.com/docs/1.1-QuickStarted)
- [术语解释](https://maafw.com/docs/1.2-ExplanationOfTerms)
- [ProjectInterface V2](https://maafw.com/docs/3.3-ProjectInterfaceV2)
- 本仓库：[如何开发](./how_to_develop.md) · [个性化配置](./custom_configure.md)
