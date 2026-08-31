# Agent 流程的 MPE 总览

本目录的 JSON 只用于在 MaaPipelineEditor 中查看 Python Custom Action 的内部阶段，
不会被 `tools/install.py` 复制到正式资源，也不能替代 `agent` 中的实际实现。

在 <https://mpe.codax.site/stable/> 中使用“导入（粘贴板）”查看：

- `竞技场-Agent流程总览.json` -> `agent/arena_loop.py`
- `芯片筛选仓库-Agent流程总览.json` -> `agent/chip_filter_flow.py`
- `第五关周本-Agent流程总览.json` -> `agent/weekly_complete.py`

正式入口仍在 `assets/interface.json`，识别节点仍在
`assets/resource/pipeline/base`。这里仅用于协作阅读，不要复制到正式 Pipeline 目录运行。
