# -*- coding: utf-8 -*-
"""读取本地 config/orders_source.json 配置的订单页 UID|关卡 列表。"""

import json
import re
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / "config" / "orders_source.json"
if not src.exists():
    raise SystemExit(f"缺少 {src} ，可参考 agent/orders_source.example.json")

url = json.loads(src.read_text(encoding="utf-8")).get("url", "").strip()
if not url:
    raise SystemExit("orders_source.json 里没有 url")

html = urllib.request.urlopen(url, timeout=15).read().decode("utf-8", errors="replace")
m = re.search(r'<div class="entry-text"[\s\S]*?<p>([\s\S]*?)</p>', html)
text = re.sub(r"<br\s*/?>", "\n", m.group(1), flags=re.I) if m else ""
text = re.sub(r"<[^>]+>", "", text)

for line in text.splitlines():
    line = line.strip()
    if "|" in line:
        print(line)
