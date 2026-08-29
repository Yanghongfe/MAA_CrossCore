<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <img alt="LOGO" src="./docs/img/logo.png" width="256" />
</p>

<div align="center">

# 交错战线助手

</div>

本项目基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 提供的项目模板进行开发，面向游戏 **《交错战线》** 的自动化助手（开发中）。

仓库地址：[Yanghongfe/MAA_Practice](https://github.com/Yanghongfe/MAA_Practice)

> [!IMPORTANT]
> **当前主线任务流依赖 / 参考了 [MCCA](https://github.com/MaaXYZ/MCCA)（交错战线社区助手）。**  
> `assets/interface.json` 任务列表、`assets/resource/pipeline/base/` 日常/周本/基建/扫荡等 pipeline，均在 MCCA 思路与资源基础上迁移、汉化与改造。  
> **非常感谢 MCCA 作者与贡献者**——没有该项目，本仓库很难在短时间内搭起可用的任务骨架。本项目仍为独立练习仓，问题请优先在本仓库提 Issues，勿直接打扰上游。

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
3. 运行解压目录中的 `MFAAvalonia.exe`（以实际文件名为准）
4. 在软件中选择控制器（安卓端 / ADB）、资源，勾选任务后开始运行

> 当前安装包显示名仍可能为模板默认的 `MaaXXX`，后续会随 `interface.json` 一并调整。

## 功能说明

> [!NOTE]
> 项目仍在早期开发。下列任务多来自 **MCCA 迁移**（见上文致谢），实机表现以勾选任务为准。

当前 `interface.json` 已挂任务（节选）：

| 任务 | 说明 |
|------|------|
| 启动游戏 | `进入首页`：StartApp / 关公告 / 签到，直到大厅 |
| 每日免费礼包 / 限时贸易 | 补给站相关 |
| 模拟军演 | 首页出击后进军演（option 可调战力阈值） |
| 基建 | 收菜 / 换班 / 好友交付等 |
| 每日探索 | 出击选择 + 通用扫荡清体力（option：关卡/层数/次数） |
| 周本 | 活动探索 · 碎星虚影等（option：关卡） |
| 领取奖励 | 邮箱 + 每日 + 通行证 |
| 关闭游戏 / 活动 / 历战试炼 | 收尾与活动向 |

自研草稿仍保留在 `pipeline/周常/`、`周本任务.json` 等，可与 base 并存，注意**节点名勿冲突**。

## 已有功能

* [x] 基于 MCCA 的任务骨架（`pipeline/base` + `interface.json`）
* [x] 官服 / B 服资源路径（B 服包名覆盖见 `resource/bilibili`）
* [x] 节点名汉化（原英文 entry 已改为中文）
* [x] Agent 示例（如 `number_lt`）
* [ ] 实机验收与选项打磨
* [ ] 自研周常与 MCCA 主线进一步整合

## 待开发功能

开发前建议先开 Issue 声明要做的内容，避免重复劳动。

* [ ] 对齐 / 精简与 MCCA 重复的旧 pipeline
* [ ] 完善项目展示名、文档与发版说明
* [ ] 更多异常弹窗兜底与稳定性
* [ ] 按需扩展 Agent 自定义逻辑

## 开发相关

* [如何开发](./docs/zh_cn/develop/how_to_develop.md)
* [本地开发手册（MuMu + MaaDebugger）](./docs/zh_cn/develop/local_dev.md)
* [PR 规范](./docs/zh_cn/develop/pull_request_guidelines.md)
* [常见问题](./docs/zh_cn/develop/faq.md)

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

**特别感谢 [MCCA](https://github.com/MaaXYZ/MCCA)**（交错战线社区助手）：当前主线任务、扫荡/出击/基建等 pipeline 结构大量参考并迁移自该项目。再次感谢作者与全体贡献者的开源工作。

感谢以下开发者对本项目作出的贡献：

<a href="https://github.com/Yanghongfe/MAA_Practice/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Yanghongfe/MAA_Practice" alt="贡献者" />
</a>

Made with [contrib.rocks](https://contrib.rocks)
