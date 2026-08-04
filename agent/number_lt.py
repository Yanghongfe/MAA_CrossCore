# -*- coding: utf-8 -*-
"""自定义识别：ROI 内 OCR 数字，小于 threshold 则命中（为真）。"""

import json
import re

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition


# 注册名必须和 pipeline 里 custom_recognition 字段一致
@AgentServer.custom_recognition("number_lt")
class NumberLessThan(CustomRecognition):
    def analyze(self, context, argv):
        # pipeline 传入的参数，例如：
        # "custom_recognition_param": { "threshold": 10, "roi": [130, 370, 36, 44] }
        try:
            param = json.loads(argv.custom_recognition_param or "{}")
        except json.JSONDecodeError:
            param = {}

        # 小于该值算命中；没写则默认 11
        threshold = int(param.get("threshold", 11))
        # 识别区域 [x, y, w, h]：优先用参数里的 roi，否则用节点 roi / 默认值
        roi = list(param.get("roi") or argv.roi or [130, 370, 36, 44])[:4]

        # 在当前截图的 roi 里跑一次 OCR（临时节点名 NumberLtOCR）
        reco = context.run_recognition(
            "NumberLtOCR",
            argv.image,
            pipeline_override={
                "NumberLtOCR": {
                    "recognition": "OCR",
                    "roi": roi,
                    "expected": [r"\d+"],  # 期望能匹配到数字
                }
            },
        )

        # 取出 OCR 最好的一条文字
        text = ""
        if reco and reco.best_result and hasattr(reco.best_result, "text"):
            text = str(reco.best_result.text)

        # 从文字里抽出第一个连续数字
        m = re.search(r"\d+", text)
        if not m:
            return None  # 没读到数字 → 未命中（假）

        value = int(m.group(0))
        if value >= threshold:
            return None  # 不小于阈值 → 未命中（假）

        # 小于阈值 → 命中（真），父节点 next 会走进这个节点
        return CustomRecognition.AnalyzeResult(box=tuple(roi), detail={"value": value})
