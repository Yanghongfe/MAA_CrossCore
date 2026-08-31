# -*- coding: utf-8 -*-
"""Warehouse-wide chip filter built from the chip-filter 1.0/2.0 recordings."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import time

import numpy as np

from maa.custom_action import CustomAction

from navigation import HOME_BUTTON, is_idle_main_ui, is_main_ui
from stop_guard import ActionStopped, ensure_running
from viewport import REFERENCE_SIZE, image_size, scale_point, scale_roi, scale_swipe


log = logging.getLogger("laa.chip_filter")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULT_FILE = PROJECT_ROOT / "config" / "chip_scan_latest.json"
PLAN_FILE = PROJECT_ROOT / "config" / "chip_filter_plan.json"
DEFAULT_PLAN_FILES = (
    PROJECT_ROOT / "default" / "chip_filter_plan.json",
    PROJECT_ROOT / "assets" / "default" / "chip_filter_plan.json",
)

MAIN_SKILLS = (
    "穿甲", "切割", "征服", "重击",
    "支援", "精力", "蓄能", "收割",
    "屏障", "铁壁", "灵巧", "暴怒",
    "致命", "腐蚀", "集中", "金刚",
    "痛击", "扩大", "物攻", "能量",
    "装填", "光幕", "钝化", "特防",
    "神威", "神力", "神速", "振奋",
    "消除", "重伤", "连击", "乘风",
    "反击", "协击", "引爆",
)
SUB_SKILLS = ("攻击", "耐久", "防御", "速度", "瞄准", "暴伤", "命中", "坚韧")
ALL_SKILLS = MAIN_SKILLS + SUB_SKILLS

WAREHOUSE_BUTTON = (1723, 63)  # 芯片筛选1.0 图1“仓库按钮”标注中心。
ITEM_TAB = (1510, 70)
CHIP_TAB = (1800, 70)          # 图4“芯片区”标注中心。
DETAIL_CLOSE_BLANK = (300, 700)
DETAIL_LOCK_TOGGLE = (1207, 158)  # 芯片筛选2.0“上锁/弃置键”标注中心。
DETAIL_LOCK_Y_OFFSET = -155
LOCKED_SCORE = 0.85
UNLOCKED_SCORE = 0.75
CHIP_SCROLLBAR_X = 1560
CHIP_SCROLLBAR_CENTER_TOP = 202
CHIP_SCROLLBAR_PAGE_STEP = 32
CHIP_SCROLL_DURATION = 320
CAPACITY_ROI = [960, 20, 330, 80]
INVENTORY_GRID_ROI = [55, 145, 1450, 790]

DECOMPOSE_BUTTON = (1813, 984)
QUICK_SELECT_BUTTON = (1752, 828)
QUALITY_BUTTONS = ((1064, 820), (1178, 824), (1323, 828), (1414, 826))
QUALITY_CONFIRM_BUTTON = (1318, 939)
DECOMPOSE_CONFIRM_BUTTON = (1800, 950)
SELL_CONFIRM_BUTTON = (1225, 675)
REWARD_DISMISS_POINT = (1438, 913)
DECOMPOSE_BACK_BUTTON = (77, 62)
DECOMPOSE_ACTION_ROI = [1500, 720, 410, 330]
DECOMPOSE_SELECTED_ROI = [1470, 80, 430, 110]
QUALITY_DIALOG_ROI = [930, 650, 570, 350]
SELL_DIALOG_ROI = [650, 380, 700, 390]
REWARD_ROI = [520, 240, 880, 650]

# The fourth row is cut off by the bottom edge. Read the three complete rows first;
# later full-inventory scanning can reuse these columns after deterministic paging.
CHIP_COLUMNS = (169, 421, 673, 925, 1177, 1429)
CHIP_ROWS = (270, 520, 765)
SCROLLED_CHIP_ROWS = (295, 545, 795)
VISIBLE_SLOTS = tuple(
    {"index": row * 6 + col + 1, "point": (x, y)}
    for row, y in enumerate(CHIP_ROWS)
    for col, x in enumerate(CHIP_COLUMNS)
)

DETAIL_NAME_ROIS = (
    [790, 308, 225, 56],
    [790, 383, 225, 56],
    [790, 458, 225, 56],
    [790, 533, 225, 56],
)
DETAIL_LEVEL_ROIS = (
    [1038, 308, 130, 56],
    [1038, 383, 130, 56],
    [1038, 458, 130, 56],
    [1038, 533, 130, 56],
)
DETAIL_NAMES_ROI = [780, 280, 270, 390]
DETAIL_LEVELS_ROI = [1020, 280, 180, 390]


def normalize_ocr(text):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or ""))


def parse_level(text):
    """Extract the only legal chip-skill levels without accepting unrelated digits."""
    normalized = normalize_ocr(text)
    match = re.search(r"(?:等级)?([123])$", normalized)
    return int(match.group(1)) if match else None


def validate_chip_detail(rows):
    """Convert four OCR rows into a typed chip detail, or reject partial reads."""
    if len(rows) != 4:
        return None
    names = [row[0] for row in rows]
    levels = [row[1] for row in rows]
    if names[0] not in MAIN_SKILLS or any(name not in SUB_SKILLS for name in names[1:]):
        return None
    if any(level not in (1, 2, 3) for level in levels):
        return None
    return {
        "main_skill": {"name": names[0], "level": levels[0]},
        "sub_skills": [
            {"name": name, "level": level}
            for name, level in zip(names[1:], levels[1:])
        ],
    }


def instance_config_path():
    configured = os.environ.get("MAA_INSTANCE_CONFIG")
    candidates = [
        Path(configured) if configured else None,
        PROJECT_ROOT / "config" / "instances" / "default.json",
        PROJECT_ROOT / "install" / "config" / "instances" / "default.json",
        PROJECT_ROOT / "gui" / "config" / "instances" / "default.json",
    ]
    return next((path for path in candidates if path and path.exists()), candidates[1])


def load_filter_plan(path=None):
    requested = Path(path) if path else PLAN_FILE
    source = requested if requested.exists() else next(
        (candidate for candidate in DEFAULT_PLAN_FILES if candidate.exists()), requested
    )
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    levels = data.get("levels", {})
    if not all(str(level) in levels for level in (1, 2, 3)):
        raise ValueError("芯片筛选方案缺少主词条等级配置")
    return data


def should_lock_chip(detail, plan):
    main = detail["main_skill"]
    level_rule = plan["levels"].get(str(main["level"]), {})
    mode = level_rule.get("mode")
    if mode == "lock":
        return True
    if mode == "unlock":
        return False
    if mode != "conditional":
        raise ValueError("芯片筛选方案包含未知处理方式：%s" % mode)

    condition = level_rule.get("conditions", {}).get(main["name"])
    if not condition:
        return False
    effective = set(condition.get("effective_sub_skills", []))
    minimum_total = int(condition.get("minimum_total_level", 0) or 0)
    if not effective or minimum_total not in (2, 3, 4, 5, 6):
        return False
    effective_total = sum(
        sub_skill["level"]
        for sub_skill in detail["sub_skills"]
        if sub_skill["name"] in effective
    )
    return effective_total >= minimum_total


class ChipFilterFlow(CustomAction):
    """Apply the saved filter plan to every chip currently stored in the warehouse."""

    @staticmethod
    def _sleep(context, seconds):
        deadline = time.time() + seconds
        while time.time() < deadline:
            ensure_running(context)
            time.sleep(min(0.1, max(0.0, deadline - time.time())))

    def _shot(self, context):
        ensure_running(context)
        image = context.tasker.controller.post_screencap().wait().get()
        self._viewport = image_size(image)
        return image

    def _click(self, context, point, label):
        ensure_running(context)
        actual = scale_point(getattr(self, "_viewport", REFERENCE_SIZE), point)
        context.tasker.controller.post_click(*actual).wait()
        log.info("按录制点击%s参考坐标(%d,%d)，实际坐标(%d,%d)", label, point[0], point[1], *actual)

    def _swipe(self, context, swipe, label):
        ensure_running(context)
        x1, y1, x2, y2, duration = scale_swipe(
            getattr(self, "_viewport", REFERENCE_SIZE), swipe
        )
        context.tasker.controller.post_swipe(x1, y1, x2, y2, duration).wait()
        log.info("执行%s拖拽(%d,%d)->(%d,%d)，时长%dms", label, x1, y1, x2, y2, duration)

    @staticmethod
    def _ocr_detail(context, image, node, roi, choices=None):
        override = {node: {"roi": scale_roi(image, roi), "threshold": 0.2}}
        if choices is not None:
            override[node]["expected"] = list(choices)
        detail = context.run_recognition(node, image, pipeline_override=override)
        return detail

    @classmethod
    def _ocr_results(cls, context, image, node, roi, choices=None):
        detail = cls._ocr_detail(context, image, node, roi, choices)
        if not detail:
            return []
        return [str(getattr(item, "text", "")) for item in (detail.all_results or [])]

    @staticmethod
    def _result_y(item):
        box = getattr(item, "box", None)
        if box is None:
            return 0
        value = getattr(box, "y", None)
        if value is not None:
            return int(value)
        try:
            return int(box[1])
        except (TypeError, IndexError):
            return 0

    @staticmethod
    def _result_height(item):
        box = getattr(item, "box", None)
        if box is None:
            return 0
        value = getattr(box, "height", None)
        if value is not None:
            return int(value)
        try:
            return int(box[3])
        except (TypeError, IndexError):
            return 0

    def _page_text(self, context, image, roi):
        try:
            return "".join(self._ocr_results(context, image, "ChipPageText", roi))
        except Exception:
            return ""

    def _saved_task_options(self):
        if os.environ.get("LAA_CHIP_FILTER_PREVIEW") == "1":
            return {"cleanup": False, "filter": True}
        try:
            data = json.loads(instance_config_path().read_text(encoding="utf-8-sig"))
            task = next(
                item for item in data.get("TaskItems", [])
                if item.get("entry") == "ChipDetailReadTask"
            )
            options = {item.get("name"): item for item in task.get("option", [])}
            return {
                "cleanup": int(options.get("清理四星及以下芯片", {}).get("index", 0)) == 1,
                "filter": int(options.get("根据自定义设置锁定/解锁仓库内芯片", {}).get("index", 0)) == 1,
            }
        except Exception as exc:
            log.warning("读取芯片筛选-仓库选项失败，按全部未勾选处理：%s", exc)
            return {"cleanup": False, "filter": False}

    def _is_chip_page(self, context, image):
        # The item page also contains both "筛选" and the inactive "芯片" tab.
        # Capacity is unique to the chip inventory and therefore avoids treating
        # the item page as an already-open chip page.
        text = " ".join(self._ocr_results(context, image, "ChipCapacity", CAPACITY_ROI))
        return re.search(r"\d{1,3}\s*[/／]\s*\d{1,3}", text) is not None

    def _is_decompose_page(self, context, image):
        text = normalize_ocr(self._page_text(context, image, DECOMPOSE_ACTION_ROI))
        return "快捷选择" in text and "确认分解" in text

    def _is_quality_dialog(self, context, image):
        text = normalize_ocr(self._page_text(context, image, QUALITY_DIALOG_ROI))
        return "1星" in text and "4星" in text and "确定" in text

    def _is_sell_dialog(self, context, image):
        text = normalize_ocr(self._page_text(context, image, SELL_DIALOG_ROI))
        return "出售" in text and "芯片" in text and "确定" in text

    def _is_reward_popup(self, context, image):
        text = normalize_ocr(self._page_text(context, image, REWARD_ROI))
        return "获得物品" in text or "点击空白处继续" in text

    def _wait_for(self, context, predicate, timeout, label):
        deadline = time.time() + timeout
        while time.time() < deadline:
            image = self._shot(context)
            if predicate(context, image):
                log.info("已确认%s", label)
                return True
            self._sleep(context, 0.18)
        log.warning("等待%s超时", label)
        return False

    def _is_warehouse(self, context, image):
        text = normalize_ocr(self._page_text(context, image, [1370, 20, 520, 105]))
        return "物品" in text or "芯片" in text

    def _is_detail_open(self, context, image):
        try:
            title = normalize_ocr(self._page_text(context, image, [850, 120, 360, 100]))
            if "芯片" in title:
                return True
            first = self._read_skill_name(context, image, 0)
            return first in MAIN_SKILLS
        except Exception:
            return False

    def _ensure_chip_page(self, context):
        for _ in range(12):
            image = self._shot(context)
            if self._is_chip_page(context, image):
                return True
            if is_idle_main_ui(context, image):
                self._click(context, (960, 540), "唤醒主界面")
            elif is_main_ui(context, image):
                self._click(context, WAREHOUSE_BUTTON, "主界面仓库按钮")
            elif self._is_warehouse(context, image):
                self._click(context, CHIP_TAB, "仓库芯片区")
            else:
                self._click(context, HOME_BUTTON, "主界面键")
            self._sleep(context, 0.9)
        return False

    def _reset_inventory_top(self, context):
        # The warehouse remembers its scroll position even after switching tabs.
        # Leaving to the main page and re-entering is the game's reliable top reset.
        self._click(context, HOME_BUTTON, "主界面键并复位芯片库存位置")
        self._sleep(context, 1.0)
        return self._ensure_chip_page(context)

    @staticmethod
    def _inventory_fingerprint(image):
        try:
            x, y, width, height = scale_roi(image, INVENTORY_GRID_ROI)
            crop = image[y:y + height, x:x + width]
            return np.asarray(crop)[::18, ::18, :3].astype(np.int16).copy()
        except Exception:
            return None

    @staticmethod
    def _inventory_changed(before, after):
        if before is None or after is None or before.shape != after.shape:
            return False
        return float(np.abs(before - after).mean()) >= 5.0

    def _scroll_to_page(self, context, page):
        before = self._inventory_fingerprint(self._shot(context))
        start_y = CHIP_SCROLLBAR_CENTER_TOP + (page - 1) * CHIP_SCROLLBAR_PAGE_STEP
        end_y = CHIP_SCROLLBAR_CENTER_TOP + page * CHIP_SCROLLBAR_PAGE_STEP
        self._swipe(
            context,
            (CHIP_SCROLLBAR_X, start_y, CHIP_SCROLLBAR_X, end_y, CHIP_SCROLL_DURATION),
            "芯片滚动条向后三行",
        )
        self._sleep(context, 0.65)
        after = self._inventory_fingerprint(self._shot(context))
        if self._inventory_changed(before, after):
            log.info("芯片库存已翻至第%d批，画面变化校验通过", page + 1)
            return True

        # A 32px reference drag becomes about 21px on a 1280x720 controller and
        # can be swallowed. A grid drag is the recorded three-row fallback.
        log.warning("滚动条微拖未改变库存画面，补偿执行三行列表拖拽")
        self._swipe(context, (1450, 900, 1450, 165, 420), "芯片列表补偿向后三行")
        self._sleep(context, 0.75)
        after = self._inventory_fingerprint(self._shot(context))
        changed = self._inventory_changed(before, after)
        if changed:
            log.info("芯片库存第%d批补偿翻页校验通过", page + 1)
        else:
            log.error("芯片库存翻页失败，停止扫描以避免重复处理第一页")
        return changed

    def _return_from_decompose(self, context):
        self._click(context, DECOMPOSE_BACK_BUTTON, "芯片分解页左上返回键")
        return self._wait_for(context, self._is_chip_page, 5.0, "返回芯片选择页面")

    def _run_cleanup(self, context):
        log.info("开始子任务：清理四星及以下芯片")
        if not self._ensure_chip_page(context):
            log.warning("无法进入仓库芯片选择页面，停止清理")
            return False
        self._click(context, DECOMPOSE_BUTTON, "批量分解")
        if not self._wait_for(context, self._is_decompose_page, 5.0, "芯片分解页面"):
            return False
        self._click(context, QUICK_SELECT_BUTTON, "快捷选择")
        if not self._wait_for(context, self._is_quality_dialog, 4.0, "快捷选择品质弹窗"):
            return False
        for level, point in enumerate(QUALITY_BUTTONS, start=1):
            self._click(context, point, "%d星芯片" % level)
            self._sleep(context, 0.12)
        self._click(context, QUALITY_CONFIRM_BUTTON, "品质选择确定")
        if not self._wait_for(context, self._is_decompose_page, 4.0, "已选择四星及以下芯片"):
            return False

        self._click(context, DECOMPOSE_CONFIRM_BUTTON, "确认分解")
        if not self._wait_for(context, self._is_sell_dialog, 2.5, "出售芯片二次确认"):
            image = self._shot(context)
            if self._is_decompose_page(context, image):
                log.info("没有可分解的四星及以下芯片，直接返回芯片选择页面")
                return self._return_from_decompose(context)
            return False
        self._click(context, SELL_CONFIRM_BUTTON, "出售芯片确定")
        if not self._wait_for(context, self._is_reward_popup, 8.0, "分解获得物品页面"):
            return False
        self._click(context, REWARD_DISMISS_POINT, "奖励页面空白处")
        if not self._wait_for(context, self._is_decompose_page, 6.0, "分解完成页面"):
            return False
        completed = self._return_from_decompose(context)
        if completed:
            log.info("子任务完成：清理四星及以下芯片，已返回芯片选择页面")
        return completed

    def _read_capacity(self, context):
        # The capacity counter rolls through intermediate values after entering
        # the tab (for example 147 before settling at 475). Wait once here so
        # an animation frame cannot truncate a full-inventory scan.
        self._sleep(context, 1.2)
        for _ in range(6):
            texts = self._ocr_results(context, self._shot(context), "ChipCapacity", CAPACITY_ROI)
            raw = " ".join(texts)
            match = re.search(r"(\d{1,3})\s*[/／]\s*(\d{1,3})", raw)
            if match:
                used, maximum = map(int, match.groups())
                if 0 <= used <= maximum <= 999:
                    log.info("识别仓库芯片容量：%d/%d", used, maximum)
                    return used
            numbers = [int(value) for value in re.findall(r"\d{1,3}", raw)]
            if len(numbers) >= 2 and 0 <= numbers[0] <= numbers[1] <= 999:
                log.info("识别仓库芯片容量：%d/%d", numbers[0], numbers[1])
                return numbers[0]
            self._sleep(context, 0.2)
        return None

    @staticmethod
    def _recognition_score(detail):
        if not detail:
            return 0.0
        candidates = [getattr(detail, "best_result", None)]
        candidates.extend(getattr(detail, "all_results", None) or [])
        scores = []
        for candidate in candidates:
            try:
                scores.append(float(getattr(candidate, "score", 0.0)))
            except (TypeError, ValueError):
                pass
        return max(scores, default=0.0)

    def _slot_lock_score(self, context, image, point):
        x, y = point
        override = {
            "ChipLockedBadge": {
                # Use a wide top-left search area. The badge shifts slightly between
                # rows and after deterministic inventory scrolling.
                "roi": scale_roi(image, [x - 145, y - 145, 120, 120]),
                "threshold": 0.1,
            }
        }
        detail = context.run_recognition("ChipLockedBadge", image, pipeline_override=override)
        return self._recognition_score(detail)

    def _read_slot_lock_state(self, context, point):
        scores = [self._slot_lock_score(context, self._shot(context), point)]
        if scores[0] >= LOCKED_SCORE:
            self._last_lock_scores = scores
            log.info("芯片栏位锁状态评分：%.3f（已锁）", scores[0])
            return True
        if scores[0] <= UNLOCKED_SCORE:
            self._last_lock_scores = scores
            log.info("芯片栏位锁状态评分：%.3f（未锁）", scores[0])
            return False

        # Only ambiguous frames pay for retries; the normal path still uses one
        # screenshot and one template match, matching the previous scan cost.
        for _ in range(2):
            self._sleep(context, 0.05)
            scores.append(self._slot_lock_score(context, self._shot(context), point))
        locked_votes = sum(score >= LOCKED_SCORE for score in scores)
        unlocked_votes = sum(score <= UNLOCKED_SCORE for score in scores)
        log.info(
            "芯片栏位锁状态评分：%s（锁定票=%d，未锁票=%d）",
            ", ".join("%.3f" % score for score in scores), locked_votes, unlocked_votes,
        )
        self._last_lock_scores = scores
        if locked_votes >= 2:
            return True
        # Ambiguous states require all three frames to agree on unlocked.
        if unlocked_votes == 3:
            return False
        return None

    def _read_skill_name(self, context, image, row):
        choices = MAIN_SKILLS if row == 0 else SUB_SKILLS
        texts = self._ocr_results(
            context, image, "ChipSkillName", DETAIL_NAME_ROIS[row], choices
        )
        normalized = [normalize_ocr(text) for text in texts]
        for choice in choices:
            if any(choice in text for text in normalized):
                return choice
        return None

    def _read_skill_level(self, context, image, row):
        texts = self._ocr_results(
            context, image, "ChipSkillLevel", DETAIL_LEVEL_ROIS[row]
        )
        for text in texts:
            level = parse_level(text)
            if level is not None:
                return level
        return None

    def _read_detail(self, context):
        readings = []
        for _ in range(4):
            image = self._shot(context)
            name_detail = self._ocr_detail(
                context, image, "ChipSkillName", DETAIL_NAMES_ROI, ALL_SKILLS
            )
            level_detail = self._ocr_detail(
                context, image, "ChipSkillLevel", DETAIL_LEVELS_ROI
            )
            names = []
            for item in (getattr(name_detail, "all_results", None) or []):
                if self._result_height(item) < 20:
                    continue
                text = normalize_ocr(getattr(item, "text", ""))
                choice = next((value for value in ALL_SKILLS if value in text), None)
                if choice:
                    names.append((self._result_y(item), choice))
            levels = []
            for item in (getattr(level_detail, "all_results", None) or []):
                level = parse_level(getattr(item, "text", ""))
                if level is not None:
                    levels.append((self._result_y(item), level))
            names.sort()
            levels.sort()
            rows = [
                (names[index][1], levels[index][1])
                for index in range(min(len(names), len(levels), 4))
            ]
            detail = validate_chip_detail(rows)
            if detail:
                viewport_height = image_size(image)[1]
                reference_name_y = round(names[0][0] * REFERENCE_SIZE[1] / viewport_height)
                detail["_lock_toggle_point"] = (
                    DETAIL_LOCK_TOGGLE[0], reference_name_y + DETAIL_LOCK_Y_OFFSET
                )
                readings.append(detail)
                if len(readings) >= 2 and readings[-1] == readings[-2]:
                    return detail
            self._sleep(context, 0.18)
        return readings[-1] if readings else None

    def _save_results(self, results, capacity, summary):
        RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.write_text(
            json.dumps(
                {
                    "schema": 2,
                    "source": "warehouse_all_chips",
                    "scan_order": "left_to_right_top_to_bottom",
                    "capacity": capacity,
                    "lock_toggle": {"x": DETAIL_LOCK_TOGGLE[0], "y": "dynamic_from_detail"},
                    "summary": summary,
                    "chips": results,
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def _process_slot(self, context, slot, plan, results, summary, dry_run=False):
        started = time.perf_counter()
        summary["attempted"] += 1
        locked_before = self._read_slot_lock_state(context, slot["point"])
        lock_scores_before = list(getattr(self, "_last_lock_scores", []))
        self._click(context, slot["point"], "第%d个芯片栏位" % slot["index"])
        self._sleep(context, 0.32)
        if not self._is_detail_open(context, self._shot(context)):
            log.warning("芯片%d未打开详情，停止本次栏位处理", slot["index"])
            summary["failed"] += 1
            return

        detail = self._read_detail(context)
        if not detail:
            log.warning("芯片%d详情未能稳定读取，已跳过且不修改锁定状态", slot["index"])
            summary["failed"] += 1
            self._click(context, DETAIL_CLOSE_BLANK, "详情外空白处")
            self._sleep(context, 0.22)
            return

        desired_locked = should_lock_chip(detail, plan)
        lock_toggle_point = tuple(detail.pop("_lock_toggle_point"))
        if locked_before is None:
            log.warning("芯片%d锁状态无法可靠确认，已读取详情但不会点击锁定区域", slot["index"])
            summary["lock_state_failed"] += 1
            self._click(context, DETAIL_CLOSE_BLANK, "详情外空白处")
            self._sleep(context, 0.25)
            detail.update({
                "slot": slot["index"],
                "locked_before": None,
                "desired_locked": desired_locked,
                "changed": False,
                "change_needed": None,
                "verified": False,
                "lock_scores_before": lock_scores_before,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "lock_toggle_point": {"x": lock_toggle_point[0], "y": lock_toggle_point[1]},
            })
            results.append(detail)
            summary["read"] += 1
            return
        changed = locked_before != desired_locked
        if changed and not dry_run:
            action = "上锁" if desired_locked else "取消上锁"
            self._click(context, lock_toggle_point, action)
            self._sleep(context, 0.3)
        self._click(context, DETAIL_CLOSE_BLANK, "详情外空白处")
        self._sleep(context, 0.25)

        verified = True
        if changed and dry_run:
            summary["planned"] += 1
        elif changed:
            state_after = self._read_slot_lock_state(context, slot["point"])
            verified = state_after == desired_locked
            if not verified and state_after == locked_before:
                log.info("芯片%d首次%s未生效，确认状态未变化后仅重试一次", slot["index"], action)
                self._click(context, slot["point"], "第%d个芯片栏位重试" % slot["index"])
                self._sleep(context, 0.32)
                if self._is_detail_open(context, self._shot(context)):
                    self._click(context, lock_toggle_point, action + "重试")
                    self._sleep(context, 0.3)
                    self._click(context, DETAIL_CLOSE_BLANK, "详情外空白处")
                    self._sleep(context, 0.25)
                    verified = self._read_slot_lock_state(context, slot["point"]) == desired_locked
            if verified:
                summary["locked" if desired_locked else "unlocked"] += 1
            else:
                summary["verify_failed"] += 1
                log.warning("芯片%d执行%s后锁定标记复核失败，不进行重复点击", slot["index"], action)
        else:
            summary["unchanged"] += 1

        detail.update({
            "slot": slot["index"],
            "locked_before": locked_before,
            "desired_locked": desired_locked,
            "changed": changed and not dry_run,
            "change_needed": changed,
            "verified": verified,
            "lock_scores_before": lock_scores_before,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "lock_toggle_point": {"x": lock_toggle_point[0], "y": lock_toggle_point[1]},
        })
        results.append(detail)
        summary["read"] += 1
        log.info(
            "芯片%d：主技能=%s%d，副技能=%s，原状态=%s，目标=%s，处理=%s，耗时=%dms",
            slot["index"], detail["main_skill"]["name"], detail["main_skill"]["level"],
            "、".join("%s%d" % (item["name"], item["level"]) for item in detail["sub_skills"]),
            "已锁" if locked_before else "未锁", "上锁" if desired_locked else "不锁",
            "仅预览" if changed and dry_run else "已切换" if changed and verified else "无需变更" if not changed else "复核失败",
            detail["elapsed_ms"],
        )

    @staticmethod
    def _remainder_slots(capacity, rows=SCROLLED_CHIP_ROWS):
        remainder = capacity % len(VISIBLE_SLOTS)
        if not remainder:
            return []
        completed = capacity - remainder
        if completed == 0:
            return [dict(VISIBLE_SLOTS[index], index=index + 1) for index in range(remainder)]

        row_count = (remainder + len(CHIP_COLUMNS) - 1) // len(CHIP_COLUMNS)
        first_visible_row = len(rows) - row_count
        slots = []
        for row in range(row_count):
            count = min(len(CHIP_COLUMNS), remainder - row * len(CHIP_COLUMNS))
            for col in range(count):
                slots.append({
                    "index": completed + row * len(CHIP_COLUMNS) + col + 1,
                    "point": (CHIP_COLUMNS[col], rows[first_visible_row + row]),
                })
        return slots

    def _run_lock_filter(self, context):
        log.info("开始子任务：根据自定义设置锁定/解锁仓库内芯片")
        if not self._ensure_chip_page(context):
            log.warning("无法进入仓库芯片区，停止筛选")
            return False
        if not self._reset_inventory_top(context):
            log.warning("仓库芯片区复位失败，停止筛选")
            return False

        capacity = self._read_capacity(context)
        if capacity is None:
            log.warning("无法可靠读取仓库芯片容量，停止筛选且不修改任何芯片")
            return False
        plan = load_filter_plan()
        dry_run = os.environ.get("LAA_CHIP_FILTER_DRY_RUN") == "1"
        scan_capacity = capacity
        if os.environ.get("LAA_CHIP_FILTER_SCAN_LIMIT"):
            requested = int(os.environ["LAA_CHIP_FILTER_SCAN_LIMIT"])
            scan_capacity = max(0, min(capacity, requested))
            log.info("芯片筛选开发验证范围：前%d/%d枚", scan_capacity, capacity)
        if dry_run:
            log.info("芯片筛选预览模式：只读取前%d/%d枚且不修改锁定状态", scan_capacity, capacity)

        results = []
        summary = {"attempted": 0, "read": 0, "locked": 0, "unlocked": 0, "unchanged": 0, "planned": 0, "failed": 0, "lock_state_failed": 0, "verify_failed": 0, "page_failed": 0}
        full_pages, remainder = divmod(scan_capacity, len(VISIBLE_SLOTS))
        for page in range(full_pages):
            page_offset = page * len(VISIBLE_SLOTS)
            rows = CHIP_ROWS if page == 0 else SCROLLED_CHIP_ROWS
            visible_slots = tuple(
                {"index": row * len(CHIP_COLUMNS) + col + 1, "point": (x, y)}
                for row, y in enumerate(rows)
                for col, x in enumerate(CHIP_COLUMNS)
            )
            for visible in visible_slots:
                slot = {"index": page_offset + visible["index"], "point": visible["point"]}
                self._process_slot(context, slot, plan, results, summary, dry_run)
            if page < full_pages - 1 or remainder:
                if not self._scroll_to_page(context, page + 1):
                    summary["page_failed"] += 1
                    self._save_results(results, capacity, summary)
                    return False

        for slot in self._remainder_slots(scan_capacity):
            self._process_slot(context, slot, plan, results, summary, dry_run)

        on_chip_page = self._is_chip_page(context, self._shot(context))
        all_slots_attempted = summary["attempted"] == scan_capacity
        self._save_results(results, capacity, summary)
        log.info(
            "锁定/解锁子任务完成检查：容量%d，计划处理%d，实际处理%d，读取%d，上锁%d，解锁%d，无需变更%d，读取失败%d，锁状态失败%d，复核失败%d，仍在芯片页=%s，结果=%s",
            capacity, scan_capacity, summary["attempted"], summary["read"], summary["locked"], summary["unlocked"], summary["unchanged"],
            summary["failed"], summary["lock_state_failed"], summary["verify_failed"], on_chip_page, RESULT_FILE,
        )
        completed = (
            all_slots_attempted
            and on_chip_page
            and summary["failed"] == 0
            and summary["lock_state_failed"] == 0
            and summary["verify_failed"] == 0
            and summary["page_failed"] == 0
        )
        if completed:
            log.info("子任务完成：根据自定义设置锁定/解锁仓库内芯片")
        return completed

    def run(self, context, argv) -> bool:
        try:
            options = self._saved_task_options()
            log.info(
                "芯片筛选-仓库勾选状态：清理四星及以下=%s，自定义锁定/解锁=%s",
                options["cleanup"], options["filter"],
            )
            if not options["cleanup"] and not options["filter"]:
                log.info("两个子任务均未勾选，芯片筛选-仓库直接完成")
                return True
            if options["cleanup"] and not self._run_cleanup(context):
                return False
            if options["filter"] and not self._run_lock_filter(context):
                return False
            log.info("芯片筛选-仓库所有已勾选子任务均已完成")
            return True
        except ActionStopped:
            log.info("检测到用户停止任务，芯片筛选立即停止且不再点击")
            return True
        except Exception as exc:
            log.exception("芯片筛选-仓库失败：%s", exc)
            return False
