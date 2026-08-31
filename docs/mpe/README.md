# Agent 流程的 MPE 总览

本目录暂存尚未迁移的历史 Python Custom Action 流程，帮助维护者在
MaaPipelineEditor 中理解现有 Agent 状态机。它们是迁移资料，不是新功能的推荐实现方式。

在 <https://mpe.codax.site/stable/> 中使用“导入（粘贴板）”查看：

- `竞技场-Agent流程总览.json` -> `agent/arena_loop.py`
- `芯片筛选仓库-Agent流程总览.json` -> `agent/chip_filter_flow.py`
- `第五关周本-Agent流程总览.json` -> `agent/weekly_complete.py`

新任务及后续重构应把页面识别、跳转、分支、循环和结束条件写入
`assets/resource/pipeline/base` 的正式可执行 Pipeline，并直接附带 `$__mpe_code`。
Agent 只保留可独立测试的 OCR、计算、配置或单次判断能力。
