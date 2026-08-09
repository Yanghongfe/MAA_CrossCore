<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <img alt="LOGO" src="./docs/img/logo.png" width="256" />
</p>

<div align="center">

# 交错战线助手

</div>

本项目基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 提供的项目模板进行开发，面向游戏 **《交错战线》** 的自动化助手（练习 / 开发中）。

仓库地址：[Yanghongfe/MAA_Practice](https://github.com/Yanghongfe/MAA_Practice)



目前主要以 GitHub Issues / 同学协作沟通为主。若后续建立 QQ 交流群，会补充到此处。

开发笔记见：[开发专用.md](./开发专用.md)

## 使用事项

> [!NOTE]
> 大部分测试基于 Windows + MuMu 模拟器。其他系统或模拟器若有问题，请提 Issues，并尽量附上程序目录下 `debug/maa.log` 与相关截图。

0. 默认面向 Windows 用户。
1. 推荐使用 [MuMu 模拟器](https://mumu.163.com/) 运行游戏；[模拟器支持情况](https://maa.plus/docs/zh-cn/manual/device/windows.html) 可参考 MAA 官方文档。
2. 模拟器建议使用 `16:9` 分辨率，例如 `1920×1080`、`1280×720`。
3. 软件内更新后若看不到新任务选项，可关闭程序后删除根目录 `config/config.json` 再打开（需重新配置部分选项）。
4. 开发调试也可用 MaaDebugger，详见 [本地开发手册](./docs/zh_cn/develop/local_dev.md)。

## 使用方式

0. 从 [Releases](https://github.com/Yanghongfe/MAA_Practice/releases) 下载 Windows 包，例如：  
   `MaaXXX-win-x86_64-v0.x.x.zip`
1. 解压压缩包
2. 确认 **MuMu 已启动且游戏可进入**
3. 运行解压目录中的 `MFW.exe`（Windows；其他平台以实际文件名为准）
4. 在软件中选择控制器（安卓端 / ADB）、资源，勾选任务后开始运行

> 当前安装包显示名仍可能为模板默认的 `MaaXXX`，后续会随 `interface.json` 一并调整。

## 功能说明

> [!NOTE]
> 项目仍在早期开发，功能完善度远低于成品助手。请以实际勾选任务与实机表现为准。

### 启动游戏

从桌面/列表识别「交错战线」进入游戏，处理常见弹窗（关 X、签到等），直至进入可操作界面附近。

### 周本（宙斯）

从「活动探索」进入碎星虚影相关流程，选择宙斯并按模板条件分支执行点击链。

### 日常刷体力（开发中）

荒墟拾遗扫荡相关 pipeline 已有草稿，**尚未挂到通用 UI 任务列表**，暂请开发者用 Debugger 调试。

## 已有功能

* [x] 启动游戏（关弹窗 / 签到流程）
* [x] 周本 · 宙斯挑战链条
* [ ] 日常刷体力（pipeline 草稿，未进 `interface.json`）
* [ ] 更多日常 / 活动 / 异常弹窗兜底

## 待开发功能

开发前建议先开 Issue 声明要做的内容，避免重复劳动。

* [ ] 将日常刷体力挂到通用 UI
* [ ] 完善 `interface.json` 项目名、说明、任务选项
* [ ] 更多周本 Boss / 日常任务
* [ ] 需要时再接入 Agent（如体力数字判断等）

## 开发相关

* [如何开发](./docs/zh_cn/develop/how_to_develop.md)
* [本地开发手册（MuMu + MaaDebugger）](./docs/zh_cn/develop/local_dev.md)
* [PR 规范](./docs/zh_cn/develop/pull_request_guidelines.md)
* [常见问题](./docs/zh_cn/develop/faq.md)

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献：

<a href="https://github.com/Yanghongfe/MAA_Practice/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Yanghongfe/MAA_Practice&v=2" alt="贡献者" />
</a>

Made with [contrib.rocks](https://contrib.rocks)
