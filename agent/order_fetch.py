# -*- coding: utf-8 -*-
"""取单加好友 + 按登记列表清理好友。

阶段：
1) 取下一单 / 输入当前UID —— 只维护 claimed_types + current，不碰「找到指定好友了」
2) 类型占完 → 跳到「加好友完毕」（后面你自己接活动；清理请另跑「拉黑订单好友」任务）
3) 取下一待删好友 / 删除登记完成 —— 在 pipeline/base/拉黑订单好友.json，按 claimed_types 逐个 OCR 拉黑并移出登记
"""

import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction

_ROOT = Path(__file__).resolve().parent.parent
STATE = _ROOT / "config" / "orders_state.json"
SOURCE = _ROOT / "config" / "orders_source.json"

_ALLOWED_HOSTS = frozenset({"rentry.org", "rentry.co"})


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"claimed_types": [], "current": None, "deleting": None}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_source_url():
    if not SOURCE.exists():
        return ""
    try:
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if isinstance(data, dict):
        return str(data.get("url") or "").strip()
    return ""


def resolve_orders_url(param: dict) -> str:
    return str((param or {}).get("url") or "").strip() or load_source_url()


def validate_orders_url(url: str) -> str | None:
    if not url:
        return f"未配置订单 URL。请创建 {SOURCE} ，内容如 {{\"url\": \"https://rentry.org/你的短链\"}}"
    try:
        u = urlparse(url)
    except Exception:
        return "订单 URL 格式无效"
    if u.scheme not in ("https",):
        return "订单 URL 仅允许 https"
    host = (u.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        return f"订单 URL 主机不在白名单: {host}"
    return None


def normalize_claimed(raw):
    out = []
    for item in raw or []:
        if isinstance(item, str) and item.strip():
            out.append({"uid": "", "type": item.strip()})
        elif isinstance(item, dict):
            uid = str(item.get("uid") or "").strip()
            typ = str(item.get("type") or "").strip()
            if typ:
                out.append({"uid": uid, "type": typ})
    return out


def claimed_type_set(claimed):
    return {c["type"] for c in claimed}


def claimed_uids(claimed):
    return [c["uid"] for c in claimed if c.get("uid")]


def override_find_friend(context, uid: str):
    """仅清理阶段：把「找到指定好友了」绑到正在删除的 uid。"""
    context.override_pipeline(
        {
            "找到指定好友了": {
                "recognition": {
                    "type": "OCR",
                    "param": {"expected": [uid]},
                }
            },
        }
    )


def fetch_orders(url):
    html = urllib.request.urlopen(url, timeout=15).read().decode("utf-8", errors="replace")
    m = re.search(r'<div class="entry-text"[\s\S]*?<p>([\s\S]*?)</p>', html)
    if not m:
        return []
    text = re.sub(r"<br\s*/?>", "\n", m.group(1), flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        uid, typ = line.split("|", 1)
        uid, typ = uid.strip(), typ.strip()
        if uid.isdigit() and 5 <= len(uid) <= 16 and typ and len(typ) <= 32 and "\n" not in typ:
            rows.append((uid, typ))
    return rows


@AgentServer.custom_action("取下一单")
class TakeNextOrder(CustomAction):
    def run(self, context, argv):
        try:
            param = json.loads(argv.custom_action_param or "{}")
        except json.JSONDecodeError:
            param = {}

        url = resolve_orders_url(param)
        err = validate_orders_url(url)
        if err:
            print(f"[取下一单] {err}")
            return False

        state = load_state()
        claimed = normalize_claimed(state.get("claimed_types"))
        types_done = claimed_type_set(claimed)
        print(f"[取下一单] claimed={claimed}")
        print(f"[取下一单] source_host={urlparse(url).hostname}")

        try:
            orders = fetch_orders(url)
        except Exception as e:
            print(f"[取下一单] fetch failed: {e}")
            return False
        print(f"[取下一单] orders={orders}")

        picked = next(((u, t) for u, t in orders if t not in types_done), None)
        if not picked:
            reason = "订单列表为空" if not orders else "可用类型已占完"
            print(f"[取下一单] {reason} → 加好友完毕（去跑活动，稍后再清理登记好友）")
            context.override_next(argv.node_name, ["加好友完毕"])
            return True

        uid, typ = picked
        claimed.append({"uid": uid, "type": typ})
        claimed.sort(key=lambda x: (x["type"], x["uid"]))
        state["claimed_types"] = claimed
        state["current"] = {"uid": uid, "type": typ}
        save_state(state)
        # 加好友阶段不覆盖「找到指定好友了」——那是清理阶段的事
        print(f"[取下一单] picked {uid}|{typ}")
        return True


def clear_input_box(context):
    ctrl = context.tasker.controller
    ctrl.post_key_down(113).wait()
    ctrl.post_click_key(29).wait()
    ctrl.post_key_up(113).wait()
    ctrl.post_click_key(67).wait()


@AgentServer.custom_action("输入当前UID")
class InputCurrentUid(CustomAction):
    def run(self, context, argv):
        state = load_state()
        cur = state.get("current") or {}
        uid = str(cur.get("uid") or "").strip()
        if not uid:
            print("[输入当前UID] no current.uid, 先跑取下一单")
            return False

        print("[输入当前UID] clear input box")
        clear_input_box(context)
        print(f"[输入当前UID] typing {uid}")
        context.tasker.controller.post_input_text(uid).wait()
        return True


@AgentServer.custom_action("取下一待删好友")
class TakeNextFriendToDelete(CustomAction):
    """从 claimed_types 取下一个有 uid 的登记，绑到「找到指定好友了」。"""

    def run(self, context, argv):
        state = load_state()
        claimed = normalize_claimed(state.get("claimed_types"))
        target = next((c for c in claimed if c.get("uid")), None)
        if not target:
            print("[取下一待删好友] 登记已空 → 清理完毕退出")
            context.override_next(argv.node_name, ["清理完毕退出"])
            return True

        uid, typ = target["uid"], target["type"]
        state["deleting"] = {"uid": uid, "type": typ}
        state["claimed_types"] = claimed
        save_state(state)
        override_find_friend(context, uid)
        print(f"[取下一待删好友] deleting {uid}|{typ} remaining={len(claimed_uids(claimed))}")
        return True


@AgentServer.custom_action("删除登记完成")
class FinishDeleteClaim(CustomAction):
    """拉黑确认后：从 claimed_types 去掉正在删除的那条。"""

    def run(self, context, argv):
        state = load_state()
        deleting = state.get("deleting") or {}
        uid = str(deleting.get("uid") or "").strip()
        claimed = normalize_claimed(state.get("claimed_types"))
        if uid:
            claimed = [c for c in claimed if c.get("uid") != uid]
            print(f"[删除登记完成] removed {uid}, left={claimed}")
        else:
            print("[删除登记完成] 无 deleting.uid，跳过移除")
        state["claimed_types"] = claimed
        state["deleting"] = None
        save_state(state)
        return True
