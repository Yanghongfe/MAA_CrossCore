# -*- coding: utf-8 -*-
"""Warehouse-wide chip filter built from the chip-filter 1.0/2.0 recordings."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import time

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
CHIP_SCROLLBAR_X = 1560
CHIP_SCROLLBAR_TOP = 170
CHIP_SCROLLBAR_PAGE_STEP = 32
CHIP_SCROLL_DURATION = 700
CAPACITY_ROI = [960, 20, 330, 80]

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
    minimum_levels = condition.get("minimum_levels", {})
    for sub_skill in detail["sub_skills"]:
        for threshold in (1, 2, 3):
            if (sub_skill["name"] in minimum_levels.get(str(threshold), [])
                    and sub_skill["level"] >= threshold):
                return True
    return False


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

    def _is_chip_page(self, context, image):
        text = normalize_ocr(self._page_text(context, image, [380, 20, 1510, 105]))
        return "筛选" in text and "芯片" in text

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

    def _scroll_to_page(self, context, page):
        start_y = CHIP_SCROLLBAR_TOP + (page - 1) * CHIP_SCROLLBAR_PAGE_STEP
        end_y = CHIP_SCROLLBAR_TOP + page * CHIP_SCROLLBAR_PAGE_STEP
        self._swipe(
            context,
            (CHIP_SCROLLBAR_X, start_y, CHIP_SCROLLBAR_X, end_y, CHIP_SCROLL_DURATION),
            "芯片滚动条向后三行",
        )
        self._sleep(context, 0.85)

    def _read_capacity(self, context):
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

    def _is_slot_locked(self, context, image, point):
        x, y = point
        override = {
            "ChipLockedBadge": {
                "roi": scale_roi(image, [x - 105, y - 105, 52, 52]),
                "threshold": 0.72,
            }
        }
        detail = context.run_recognition("ChipLockedBadge", image, pipeline_override=override)
        return bool(detail and detail.hit)

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
                detail["_lock_toggle_point"] = DETAIL_LOCK_TOGGLE
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
        image = self._shot(context)
        locked_before = self._is_slot_locked(context, image, slot["point"])
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
            verified = self._is_slot_locked(context, self._shot(context), slot["point"]) == desired_locked
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
            "lock_toggle_point": {"x": lock_toggle_point[0], "y": lock_toggle_point[1]},
        })
        results.append(detail)
        summary["read"] += 1
        log.info(
            "芯片%d：主技能=%s%d，副技能=%s，原状态=%s，目标=%s，处理=%s",
            slot["index"], detail["main_skill"]["name"], detail["main_skill"]["level"],
            "、".join("%s%d" % (item["name"], item["level"]) for item in detail["sub_skills"]),
            "已锁" if locked_before else "未锁", "上锁" if desired_locked else "不锁",
            "仅预览" if changed and dry_run else "已切换" if changed and verified else "无需变更" if not changed else "复核失败",
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

    def run(self, context, argv) -> bool:
        try:
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
            summary = {"read": 0, "locked": 0, "unlocked": 0, "unchanged": 0, "planned": 0, "failed": 0, "verify_failed": 0}
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
                    self._scroll_to_page(context, page + 1)

            for slot in self._remainder_slots(scan_capacity):
                self._process_slot(context, slot, plan, results, summary, dry_run)

            self._save_results(results, capacity, summary)
            log.info(
                "芯片筛选-仓库完成：容量%d，读取%d，上锁%d，解锁%d，无需变更%d，读取失败%d，复核失败%d，结果=%s",
                capacity, summary["read"], summary["locked"], summary["unlocked"], summary["unchanged"],
                summary["failed"], summary["verify_failed"], RESULT_FILE,
            )
            return summary["failed"] == 0 and summary["verify_failed"] == 0
        except ActionStopped:
            log.info("检测到用户停止任务，芯片筛选立即停止且不再点击")
            return True
        except Exception as exc:
            log.exception("芯片筛选-仓库失败：%s", exc)
            return False
