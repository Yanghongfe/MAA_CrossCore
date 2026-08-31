# -*- coding: utf-8 -*-
"""Run the recorded weekly Zeus route and choose one of four map paths."""
import json
import logging
import os
import re
import time
from pathlib import Path

import numpy as np
from maa.custom_action import CustomAction

from navigation import (
    BACK_BUTTON,
    HOME_BUTTON,
    IDLE_MAIN_WAKE,
    is_idle_main_ui,
    is_main_ui,
    main_control_point,
    page_distance,
    should_return_home,
)
from stop_guard import ActionStopped, ensure_running
from viewport import REFERENCE_SIZE, image_size, scale_point, scale_roi, scale_swipe


log = logging.getLogger("weekly")
log.setLevel(logging.INFO)
if not log.handlers:
    log.addHandler(logging.StreamHandler())

MAIN_ATTACK = main_control_point("sortie")
ACTIVITY_EXPLORE = (962, 227)
WEEKLY_SHATTERED_STAR = (961, 579)
GORI_PHANTOM = (400, 708)
ZEUS_PHANTOM = (959, 670)
START_BATTLE = (1681, 991)
BOSS_SCROLL = (950, 850, 950, 300, 700)
BOSS_CORNER_TARGET = (1036, 324)
BOSS_CORNER_SWIPE = (960, 120, 960, 900, 1200)
BOSS_CORNER_MARKER_X = (970, 1100)
BOSS_CORNER_MARKER_Y = (55, 155)
ROUTE_CORNER_SWIPE = (960, 900, 960, 120, 1200)
ROUTE_CORNER_ANCHOR = (686, 124)
ROUTE_CORNER_SPAWN = (718, 491)
MOVE_STEP_WAIT = 4.2
ENEMY_TURN_WAIT = 8.5
FINAL_MOVE_WAIT = 2.0
MAP_STUCK_TIMEOUT = 20.0
MAX_MAP_RESTARTS = 2

ROI_ZEUS_CARD = [658, 581, 574, 173]
ROI_MAP_TOP = [1515, 18, 355, 105]
ROI_MAP_BOTTOM = [65, 870, 330, 175]

SECOND_TEAM_CLOSE = (1760, 565)
START_ACTION = (1735, 965)
SKIP_BATTLE = (1745, 85)
REWARD_DISMISS = (1440, 805)
RESULT_CONTINUE = (1328, 691)
NO_REWARD_CONFIRM = (1205, 675)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STOP_WHEN_FULL_OPTION = "本周报酬全部领取后结束"
WEEKLY_COUNT_OPTION = "周本自定次数"
PAGE_LABELS = {
    "main": "主界面",
    "main_idle": "主界面待机画面",
    "secondary": "二级菜单",
    "activity_choice": "活动选择页",
    "weekly_choice": "周本选择页",
    "boss_choice": "BOSS选择页",
    "battle_prep": "战斗准备页",
    "map": "周本地图",
    "reward": "周本获得物品页",
    "victory": "周本战斗胜利页",
    "arena_hub": "模拟军演页",
    "arena": "竞技场列表页",
    "unknown": "未识别页面",
}

WEEKLY_RECOGNITION_ROIS = {
    "WeeklySpawnCharacter": [430, 430, 930, 520],
    "WeeklySpawnMarker": [430, 350, 930, 500],
    "WeeklyMonster3Shield": [610, 245, 720, 500],
    "WeeklyRouteAnchor": [400, 40, 950, 500],
    "WeeklyBossMarker": [650, 0, 700, 380],
    "WeeklyPageText": [0, 0, 1920, 1080],
    "WeeklySelectedBoss": [1270, 75, 620, 120],
    "WeeklySkip": [1600, 15, 280, 135],
    "WeeklyPlayerTurn": [1260, 900, 330, 155],
    "WeeklyResult": [0, 0, 680, 260],
    "WeeklyRewardPopup": [500, 150, 920, 720],
    "WeeklyVictoryPage": [0, 0, 960, 430],
    "WeeklyNoRewardConfirm": [450, 390, 1050, 190],
    "WeeklyReadProgress": [90, 880, 500, 175],
}
WEEKLY_SCALED_TEMPLATES = {
    "WeeklySpawnCharacter": ["weekly_spawn1_character_720.png", "weekly_spawn2_character_720.png"],
    "WeeklyMonster3Shield": "weekly_monster3_shield_720.png",
    "WeeklyRouteAnchor": "weekly_route_anchor_720.png",
    "WeeklySkip": "weekly_skip_720.png",
    "WeeklyResult": "weekly_result_720.png",
}

# Camera setup and movement taps copied from the four completed recordings.
CASES = {
    1: {
        "name": "出生点1 + 怪1",
        "camera": [(560, 535, 1121, 948, 887), (859, 701, 846, 499, 896)],
        "moves": [(828, 472), (864, 398), (1129, 291), (1076, 304), (1048, 317)],
    },
    2: {
        "name": "出生点1 + 怪3（大盾）",
        "camera": [
            (1225, 721, 1442, 447, 929),
            (750, 224, 1204, 717, 994),
            (1245, 803, 1121, 168, 2106),
        ],
        "moves": [(815, 504), (812, 587), (809, 390), (936, 249), BOSS_CORNER_TARGET],
    },
    3: {
        "name": "出生点2 + 怪1",
        "camera": [
            (714, 337, 1168, 779, 926),
            (1237, 784, 1323, 782, 424),
            (1155, 865, 841, 285, 850),
        ],
        "moves": [(1110, 551), (1074, 623), (1040, 571), (1123, 451), (968, 229), (1019, 324)],
    },
    4: {
        "name": "出生点2 + 怪3（大盾）",
        "camera": [(731, 407, 1443, 963, 2139), (1320, 919, 1132, 385, 904)],
        "moves": [(1113, 561), (1102, 447), (949, 226), (1043, 304)],
    },
}


class WeeklyFlow(CustomAction):
    def __init__(self):
        super().__init__()
        self._weekly_full = False
        self.last_case_id = None
        self.last_run_success = False
        self._retry_requested = False

    @staticmethod
    def _instance_config():
        configured = os.environ.get("MAA_INSTANCE_CONFIG")
        candidates = [
            Path(configured) if configured else None,
            PROJECT_ROOT / "config" / "instances" / "default.json",
            PROJECT_ROOT / "gui" / "config" / "instances" / "default.json",
        ]
        return next((path for path in candidates if path and path.is_file()), None)

    @classmethod
    def _saved_weekly_task(cls):
        config_path = cls._instance_config()
        if config_path is None:
            return None
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return next(
            item for item in data.get("TaskItems", [])
            if item.get("entry") in ("WeeklyTask", "周本")
        )

    @classmethod
    def _stop_when_rewards_full(cls):
        """Read the live MFA checkbox value; checkbox indices are stored as a list."""
        try:
            task = cls._saved_weekly_task()
            if task is None:
                return True
            option = next(
                item for item in task.get("option", [])
                if item.get("name") == STOP_WHEN_FULL_OPTION
            )
            selected_cases = option.get("selected_cases")
            if isinstance(selected_cases, list):
                return any(value in selected_cases for value in ("Yes", "开启", STOP_WHEN_FULL_OPTION))
            index = option.get("index", [])
            if isinstance(index, list):
                return 0 in index
            return index == 0
        except Exception as exc:
            log.info("当前周本任务未配置600/600结束选项，按单次任务执行：%s", exc)
            return True

    @classmethod
    def _target_runs(cls):
        try:
            task = cls._saved_weekly_task()
            if task is None:
                return 5
            option = next(
                item for item in task.get("option", [])
                if item.get("name") == WEEKLY_COUNT_OPTION
            )
            selected_cases = option.get("selected_cases")
            if isinstance(selected_cases, list) and selected_cases:
                return max(1, min(10, int(selected_cases[0])))
            index = option.get("index", 4)
            if isinstance(index, list):
                index = index[0] if index else 4
            return max(1, min(10, int(index) + 1))
        except Exception as exc:
            log.warning("读取周本自定次数失败，使用默认5次：%s", exc)
            return 5

    def _shot(self, ctx):
        ensure_running(ctx)
        image = ctx.tasker.controller.post_screencap().wait().get()
        self._viewport = image_size(image)
        return image

    def _click(self, ctx, point, label):
        ensure_running(ctx)
        actual = scale_point(getattr(self, "_viewport", REFERENCE_SIZE), point)
        ctx.tasker.controller.post_click(*actual).wait()
        log.info(
            "按录制点击%s参考坐标(%d,%d)，实际坐标(%d,%d)",
            label, point[0], point[1], actual[0], actual[1],
        )

    def _click_viewport(self, ctx, point, label):
        ensure_running(ctx)
        ctx.tasker.controller.post_click(*point).wait()
        log.info("点击%s当前坐标(%d,%d)", label, point[0], point[1])

    def _click_recognized_center(self, context, node, image, label, fallback):
        hit, detail = self._recognized(context, node, image)
        if hit and detail is not None:
            box = detail.box
            point = (box.x + box.w // 2, box.y + box.h // 2)
            self._click_viewport(context, point, "%s识别框中心" % label)
            return True
        self._click(context, fallback, "%s固定位置兜底" % label)
        return False

    def _swipe(self, ctx, swipe, label):
        ensure_running(ctx)
        x1, y1, x2, y2, duration = scale_swipe(
            getattr(self, "_viewport", REFERENCE_SIZE), swipe
        )
        ctx.tasker.controller.post_swipe(x1, y1, x2, y2, duration).wait()
        log.info("%s实际拖拽：(%d,%d)到(%d,%d)", label, x1, y1, x2, y2)

    @staticmethod
    def _color_ratio(img, roi, kind):
        try:
            x, y, w, h = scale_roi(img, roi)
            crop = img[y:y + h:4, x:x + w:4]
            if crop.size == 0:
                return 0.0
            c0, c1, c2 = (crop[:, :, i].astype("int16") for i in range(3))
            if kind == "cyan":
                mask = ((c0 < 120) & (c1 > 145) & (c2 > 130)) | ((c2 < 120) & (c1 > 145) & (c0 > 130))
            else:
                mask = (c0 > 205) & (c1 > 205) & (c2 > 205)
            return float(mask.mean())
        except Exception as exc:
            log.warning("关键区域颜色检测失败：%s", exc)
            return 0.0

    def _is_main(self, context, img):
        return is_main_ui(context, img)

    def _is_map_ready(self, img):
        return self._color_ratio(img, ROI_MAP_TOP, "white") > 0.025 and self._color_ratio(img, ROI_MAP_BOTTOM, "white") > 0.018

    def _screen_text(self, context, image):
        try:
            detail = self._run_recognition(context, "WeeklyPageText", image)
            if not detail:
                return ""
            return " ".join(
                str(getattr(item, "text", "")) for item in (detail.all_results or [])
            )
        except Exception as exc:
            log.warning("周本页面文字识别失败：%s", exc)
            return ""

    def _detect_page(self, context, image):
        if self._is_main(context, image):
            return "main"
        if is_idle_main_ui(context, image):
            return "main_idle"
        arena_hit, _ = self._recognized(context, "ArenaRefresh", image)
        if arena_hit:
            return "arena"
        text = self._screen_text(context, image)
        reward_hit, _ = self._recognized(context, "WeeklyRewardPopup", image)
        if reward_hit or ("获得物品" in text and "周报酬" in text):
            return "reward"
        victory_hit, _ = self._recognized(context, "WeeklyVictoryPage", image)
        if victory_hit or "战斗胜利" in text:
            return "victory"
        if "刷新对手" in text or "对手阵容" in text:
            return "arena"
        if "模拟军演" in text and ("镜像竞技" in text or "军演竞技" in text):
            return "arena_hub"
        # Broad map color checks must run after distinctive cross-task pages.
        if self._is_map_ready(image):
            return "map"
        if "开始行动" in text:
            return "battle_prep"
        if "开始战斗" in text:
            return "boss_choice"
        if "戈里刻虚影" in text:
            return "weekly_choice"
        if "碎星虚影" in text:
            return "activity_choice"
        if "活动探索" in text:
            return "secondary"
        return "unknown"

    @staticmethod
    def _yellow_edge_ratio(img, roi):
        try:
            x, y, w, h = scale_roi(img, roi)
            crop = img[y:y + h, x:x + w]
            edge = np.zeros(crop.shape[:2], dtype=bool)
            edge[:20, :] = edge[-20:, :] = True
            edge[:, :20] = edge[:, -20:] = True
            pixels = crop[edge][::4]
            c0, c1, c2 = (pixels[:, i].astype("int16") for i in range(3))
            mask = ((c0 > 170) & (c1 > 110) & (c2 < 130)) | ((c2 > 170) & (c1 > 110) & (c0 < 130))
            return float(mask.mean())
        except Exception as exc:
            log.warning("宙斯黄框检测失败：%s", exc)
            return 0.0

    def _run_recognition(self, context, node, image):
        roi = WEEKLY_RECOGNITION_ROIS.get(node)
        if roi is None:
            return context.run_recognition(node, image)
        params = {"roi": scale_roi(image, roi)}
        template = WEEKLY_SCALED_TEMPLATES.get(node)
        if template is not None and image_size(image) != REFERENCE_SIZE:
            params["template"] = template
        return context.run_recognition(node, image, pipeline_override={node: params})

    def _recognized(self, context, node, image):
        detail = self._run_recognition(context, node, image)
        return bool(detail and detail.hit), detail

    def _wait_for(self, context, predicate, timeout, label, interval=0.55):
        deadline = time.time() + timeout
        while time.time() < deadline:
            ensure_running(context)
            image = self._shot(context)
            if predicate(image):
                log.info("已识别%s", label)
                return image
            time.sleep(interval)
        log.warning("等待%s超时", label)
        return None

    def _wait_map_stable(self, context, timeout=6.0):
        deadline = time.time() + timeout
        previous = None
        stable = 0
        while time.time() < deadline:
            ensure_running(context)
            image = self._shot(context)
            x, y, width, height = scale_roi(image, [350, 150, 1150, 750])
            crop = image[y:y + height:8, x:x + width:8].astype("int16")
            if previous is not None and float(np.abs(crop - previous).mean()) < 5.5:
                stable += 1
                if stable >= 2:
                    return True
            else:
                stable = 0
            previous = crop
            time.sleep(0.45)
        log.info("地图仍有动画，使用最长等待后继续")
        return False

    def _navigate_to_weekly(self, context):
        """Continue from any known weekly entry page without backing out first."""
        unknown_count = 0
        home_fallback_used = False
        actions = {
            "main_idle": (IDLE_MAIN_WAKE, "主界面待机画面空白处"),
            "secondary": (ACTIVITY_EXPLORE, "二级菜单活动探索键"),
            "activity_choice": (WEEKLY_SHATTERED_STAR, "碎星虚影区域"),
            "weekly_choice": (GORI_PHANTOM, "戈里刻虚影区域"),
            "arena_hub": (BACK_BUTTON, "模拟军演页返回二级菜单键"),
        }
        for _ in range(10):
            ensure_running(context)
            image = self._shot(context)
            page = self._detect_page(context, image)
            log.info("周本接续导航：当前页面=%s", PAGE_LABELS[page])
            if page in ("boss_choice", "battle_prep"):
                return page
            if page == "reward":
                if not self._dismiss_weekly_reward(context):
                    return None
                continue
            if page == "victory":
                if not self._dismiss_weekly_victory(context):
                    return None
                continue
            if page == "main":
                self._click_recognized_center(
                    context,
                    "NavMainSortie",
                    image,
                    "主界面出击键",
                    MAIN_ATTACK,
                )
                left_main = self._wait_for(
                    context,
                    lambda shot: self._detect_page(context, shot) not in ("main", "main_idle"),
                    6.0,
                    "离开主界面进入二级菜单",
                )
                if left_main is None:
                    log.warning("主界面出击点击未生效，下一轮重新识别后重试")
                continue
            if should_return_home(page, "activity_choice"):
                distance = page_distance(page, "activity_choice")
                log.info(
                    "跨任务页面距离=%s，超过2页，点击主界面键后重新进入周本",
                    distance,
                )
                self._click(context, HOME_BUTTON, "跨任务交接主界面键")
                image = self._wait_for(
                    context,
                    lambda shot: self._is_main(context, shot),
                    8.0,
                    "跨任务交接后的主界面",
                )
                if image is None:
                    return None
                continue
            action = actions.get(page)
            if action is not None:
                unknown_count = 0
                self._click(context, action[0], action[1])
                time.sleep(1.5)
                continue
            if page == "map":
                log.warning("检测到仍在旧周本地图，先撤退再重新开局判断")
                self._retreat_stuck_map(context, "接续任务发现旧周本地图")
                return None
            unknown_count += 1
            if unknown_count < 2:
                time.sleep(0.8)
                continue
            if home_fallback_used:
                log.warning("周本接续导航仍无法辨认页面，停止本轮")
                return None
            log.warning("连续两次无法辨认页面，仅使用一次主界面键兜底")
            self._click(context, HOME_BUTTON, "主界面键兜底")
            home_fallback_used = True
            unknown_count = 0
            time.sleep(2.0)
        return None

    def _select_zeus(self, context):
        selected = self._screen_text_region(context, self._shot(context), "WeeklySelectedBoss")
        if "虚影宙斯" in selected:
            log.info("当前已选中虚影宙斯，直接接续开始战斗")
            return True
        self._swipe(context, BOSS_SCROLL, "在BOSS栏向上拖拽")
        time.sleep(1.5)
        for attempt in range(2):
            self._click(context, ZEUS_PHANTOM, "虚影宙斯区域")
            time.sleep(1.2)
            image = self._shot(context)
            selected = self._screen_text_region(context, image, "WeeklySelectedBoss")
            if "虚影宙斯" in selected:
                log.info("已通过右侧标题确认选中虚影宙斯")
                return True
            ratio = self._yellow_edge_ratio(image, ROI_ZEUS_CARD)
            log.info("虚影宙斯黄框比例=%.3f", ratio)
            if ratio >= 0.018:
                log.info("已通过宙斯卡片黄框关键部分确认选中")
                return True
            log.warning("未确认宙斯黄框，准备重试：%d/2", attempt + 1)
        return False

    def _screen_text_region(self, context, image, node):
        try:
            detail = self._run_recognition(context, node, image)
            if not detail:
                return ""
            return " ".join(
                str(getattr(item, "text", "")) for item in (detail.all_results or [])
            )
        except Exception as exc:
            log.warning("读取周本局部文字失败(%s)：%s", node, exc)
            return ""

    def _detect_spawn(self, context, image):
        hit, detail = self._recognized(context, "WeeklySpawnMarker", image)
        source = "角色头顶01标记"
        if not hit or detail is None:
            hit, detail = self._recognized(context, "WeeklySpawnCharacter", image)
            source = "旧角色外观兜底"
        if not hit or detail is None:
            log.warning("未识别到角色头顶01标记或出生人物兜底特征")
            return None
        center_x = detail.box.x + detail.box.w / 2
        split_x = scale_point(image_size(image), (900, 0))[0]
        spawn = 1 if center_x < split_x else 2
        log.info("出生点识别来源=%s，匹配框=%s，判定出生点%d", source, detail.box, spawn)
        return spawn

    @staticmethod
    def _recognition_score(detail):
        """Return the strongest template score, including results below threshold."""
        results = list(getattr(detail, "all_results", None) or [])
        best = getattr(detail, "best_result", None)
        if best is not None:
            results.append(best)
        scores = [float(getattr(item, "score", 0.0) or 0.0) for item in results]
        return max(scores, default=0.0)

    def _detect_shield(self, context, image):
        # A moving map can resemble part of the shield for one frame. Require the
        # recorded shield feature to persist, while still matching only that feature.
        hits = 0
        for frame_index in range(3):
            hit, detail = self._recognized(context, "WeeklyMonster3Shield", image)
            score = self._recognition_score(detail)
            log.info(
                "大盾确认帧%d/3：%s，最高匹配分数=%.3f",
                frame_index + 1,
                "命中" if hit else "未命中",
                score,
            )
            if hit:
                hits += 1
                if hits >= 2:
                    log.info("大盾关键部位连续确认通过，判定怪3")
                    return True
            if hits + (2 - frame_index) < 2:
                break
            time.sleep(0.25)
            image = self._shot(context)
        log.info("大盾关键部位未通过多帧确认，判定怪1")
        return False

    def _read_weekly_progress(self, context):
        try:
            image = self._shot(context)
            detail = self._run_recognition(context, "WeeklyReadProgress", image)
            if not detail or not detail.hit:
                return None
            texts = [str(getattr(item, "text", "")) for item in detail.all_results]
            text = " ".join(texts)
            match = re.search(r"(\d+)\s*/\s*(\d+)", text)
            if not match:
                log.warning("未从周本进度OCR结果解析出分数：%s", text)
                return None
            current, total = map(int, match.groups())
            log.info("周本进度识别=%d/%d", current, total)
            return current, total
        except Exception as exc:
            log.warning("周本进度识别失败：%s", exc)
            return None

    def _identify_map(self, context, image):
        spawn = self._detect_spawn(context, image)
        if spawn is None:
            return None

        if spawn == 1:
            probe_camera = CASES[2]["camera"][:2]
            shield_case = 2
        else:
            probe_camera = CASES[4]["camera"][:1]
            shield_case = 4
        for index, swipe in enumerate(probe_camera, 1):
            self._swipe(context, swipe, "出生点%d观察怪物镜头%d" % (spawn, index))
            self._wait_map_stable(context, 3.5)

        has_shield = self._detect_shield(context, self._shot(context))
        if has_shield:
            case_id = shield_case
            camera_done = len(probe_camera)
        else:
            case_id = 1 if spawn == 1 else 3
            # Every recorded camera gesture moves toward the boss. Do not reverse
            # toward the player; replay the selected route to settle at its boss edge.
            camera_done = 0
        log.info("周本情况判定完成：情况%d（%s）", case_id, CASES[case_id]["name"])
        return case_id, camera_done

    def _prepare_and_identify(self, context):
        self._click(context, SECOND_TEAM_CLOSE, "第二队关闭键")
        time.sleep(0.6)
        self._click(context, START_ACTION, "开始行动")
        image = self._wait_for(context, self._is_map_ready, 25.0, "周本地图正常操作界面")
        if image is None:
            return None
        return self._identify_map(context, image)

    def _run_map_route(self, context, case_id, camera_done=0):
        for index in range(2):
            self._swipe(
                context,
                ROUTE_CORNER_SWIPE,
                "情况%d统一拖到地图左下角%d/2" % (case_id, index + 1),
            )
            self._wait_map_stable(context, 3.5)
        if not self._normalize_route_anchor(context, case_id):
            return False
        return self._run_case_moves(context, case_id)

    def _normalize_route_anchor(self, context, case_id):
        for attempt in range(3):
            image = self._shot(context)
            hit, detail = self._recognized(context, "WeeklyRouteAnchor", image)
            source = "静态障碍物"
            if hit and detail is not None:
                current_x, current_y = detail.box.x, detail.box.y
                expected_x, expected_y = scale_point(image_size(image), ROUTE_CORNER_ANCHOR)
            else:
                hit, detail = self._recognized(context, "WeeklySpawnMarker", image)
                source = "角色头顶01辅助"
                if not hit or detail is None:
                    log.warning("情况%d路线归一未识别到静态地图锚点或01辅助锚点", case_id)
                    time.sleep(0.4)
                    continue
                current_x = detail.box.x + detail.box.w // 2
                current_y = detail.box.y + detail.box.h // 2
                expected_x, expected_y = scale_point(image_size(image), ROUTE_CORNER_SPAWN)
            offset_x = current_x - expected_x
            offset_y = current_y - expected_y
            log.info(
                "情况%d左下角锚点来源=%s，当前=(%d,%d)，目标=(%d,%d)，偏差=(%d,%d)",
                case_id,
                source,
                current_x,
                current_y,
                expected_x,
                expected_y,
                offset_x,
                offset_y,
            )
            tolerance = max(12, scale_point(image_size(image), (24, 24))[0])
            if abs(offset_x) <= tolerance and abs(offset_y) <= tolerance:
                log.info("情况%d已确认处于地图左下角固定视角", case_id)
                return True
            if attempt < 2:
                self._swipe(
                    context,
                    ROUTE_CORNER_SWIPE,
                    "情况%d左下角边界补充拖拽%d/2" % (case_id, attempt + 1),
                )
                self._wait_map_stable(context, 3.5)
        log.error("情况%d视角未能归一到静态地图或01辅助锚点，停止路线以避免固定坐标误点", case_id)
        return False

    def _run_case_moves(self, context, case_id, start_index=0):
        case = CASES[case_id]
        for index, point in enumerate(case["moves"][start_index:], start_index + 1):
            ensure_running(context)
            if case_id == 2 and index == len(case["moves"]):
                if not self._click_visible_boss(context, self._shot(context)):
                    log.error("情况2末步未能确认并点击最上角固定BOSS点")
                    return False
            else:
                self._click(context, point, "情况%d左下角固定移动%d" % (case_id, index))
            if index < len(case["moves"]):
                if index % 2 == 0:
                    log.info("情况%d等待怪物回合固定%.1f秒", case_id, ENEMY_TURN_WAIT)
                    time.sleep(ENEMY_TURN_WAIT)
                else:
                    time.sleep(MOVE_STEP_WAIT)
            else:
                time.sleep(FINAL_MOVE_WAIT)
        return True

    def _click_visible_boss(self, context, image):
        hit, detail = self._recognized(context, "WeeklyBossMarker", image)
        if hit and detail is not None:
            log.info("拖拽前已识别BOSS标记%s", detail.box)
        else:
            log.info("BOSS附近暂未显示标记，直接竖直下拖到地图最上角后再识别")
        last_detail = None
        for index in range(2):
            self._swipe(
                context,
                BOSS_CORNER_SWIPE,
                "BOSS接敌前拖到地图最上角%d/2" % (index + 1),
            )
            self._wait_map_stable(context, 3.5)
            hit, last_detail = self._recognized(context, "WeeklyBossMarker", self._shot(context))
            if not hit or last_detail is None:
                last_detail = None
                continue
            box = last_detail.box
            marker_x = box.x + box.w // 2
            marker_y = box.y + box.h // 2
            min_marker = scale_point(image_size(image), (BOSS_CORNER_MARKER_X[0], BOSS_CORNER_MARKER_Y[0]))
            max_marker = scale_point(image_size(image), (BOSS_CORNER_MARKER_X[1], BOSS_CORNER_MARKER_Y[1]))
            if (
                min_marker[0] <= marker_x <= max_marker[0]
                and min_marker[1] <= marker_y <= max_marker[1]
            ):
                log.info("第%d次拖拽已到地图最上角，省略后续拖拽", index + 1)
                break
        if last_detail is None:
            log.warning("拖到地图最上角后未重新识别到BOSS，取消点击")
            return False

        box = last_detail.box
        marker_x = box.x + box.w // 2
        marker_y = box.y + box.h // 2
        viewport = image_size(self._shot(context))
        min_marker = scale_point(viewport, (BOSS_CORNER_MARKER_X[0], BOSS_CORNER_MARKER_Y[0]))
        max_marker = scale_point(viewport, (BOSS_CORNER_MARKER_X[1], BOSS_CORNER_MARKER_Y[1]))
        if (
            min_marker[0] <= marker_x <= max_marker[0]
            and min_marker[1] <= marker_y <= max_marker[1]
        ):
            target = BOSS_CORNER_TARGET
            label = "最上角视角固定BOSS接敌点"
            log.info("最上角BOSS锚点%s符合实机范围，使用固定坐标%s", box, target)
            self._click(context, target, label)
        else:
            target = (marker_x, min(viewport[1] - 1, box.y + round(232 * viewport[1] / 1080)))
            label = "按BOSS锚点补正的接敌点"
            log.warning("BOSS锚点%s偏离最上角实机范围，改用锚点补正坐标%s", box, target)
            self._click_viewport(context, target, label)
        return True

    def _retreat_stuck_map(self, context, reason):
        """Leave a stalled map so the next attempt starts from a clean state."""
        if not self._is_map_ready(self._shot(context)):
            return False
        log.warning("%s，退出本局并重新进入判断", reason)
        self._wait_map_stable(context, 6.0)
        time.sleep(1.0)
        for attempt in range(3):
            self._click(context, (164, 60), "卡住后左上返回键")
            time.sleep(2.0)
            self._click(context, NO_REWARD_CONFIRM, "卡住后撤退确认")
            image = self._wait_for(
                context,
                lambda shot: self._detect_page(context, shot) == "boss_choice",
                10.0,
                "撤退后的BOSS选择页",
            )
            if image is not None:
                self._retry_requested = True
                return True
            log.warning("第%d次撤退后仍未返回BOSS选择页", attempt + 1)
        return False

    def _dismiss_weekly_reward(self, context):
        for attempt in range(3):
            self._click(context, REWARD_DISMISS, "周本奖励页空白处")
            image = self._wait_for(
                context,
                lambda shot: self._detect_page(context, shot) in ("victory", "boss_choice"),
                5.0,
                "奖励后的战斗胜利页或BOSS选择页",
            )
            if image is not None:
                if self._detect_page(context, image) == "boss_choice":
                    log.info("周本奖励已关闭并返回BOSS选择页")
                    return True
                return self._dismiss_weekly_victory(context)

            current = self._detect_page(context, self._shot(context))
            if current != "reward":
                log.warning("奖励页已离开但下一结算状态暂未识别，继续等待")
                image = self._wait_for(
                    context,
                    lambda shot: self._detect_page(context, shot) in ("victory", "boss_choice"),
                    5.0,
                    "延迟出现的战斗胜利页或BOSS选择页",
                )
                if image is not None:
                    if self._detect_page(context, image) == "boss_choice":
                        return True
                    return self._dismiss_weekly_victory(context)
            log.warning("周本奖励页第%d次点击未生效，重新识别后点击", attempt + 1)
        log.warning("周本奖励页连续点击后仍未进入下一结算状态")
        return False

    def _dismiss_weekly_victory(self, context):
        for attempt in range(3):
            self._click(context, RESULT_CONTINUE, "战斗胜利页继续空白处")
            image = self._wait_for(
                context,
                lambda shot: self._detect_page(context, shot) == "boss_choice",
                5.0,
                "战斗胜利后的BOSS选择页",
            )
            if image is not None:
                log.info("周本奖励与胜利结算处理完成，已返回BOSS选择页")
                return True
            log.warning("战斗胜利页第%d次点击未返回BOSS页，重新确认后点击", attempt + 1)
        return False

    def _finish_battle(self, context):
        deadline = time.time() + 100
        skip_was_visible = False
        map_stuck_since = None
        while time.time() < deadline:
            ensure_running(context)
            image = self._shot(context)
            reward_hit, _ = self._recognized(context, "WeeklyRewardPopup", image)
            if reward_hit:
                if not self._dismiss_weekly_reward(context):
                    return False
                log.info("周本单次流程完成")
                return True
            victory_hit, _ = self._recognized(context, "WeeklyVictoryPage", image)
            if victory_hit:
                if not self._dismiss_weekly_victory(context):
                    return False
                log.info("周本单次流程完成")
                return True
            result_hit, _ = self._recognized(context, "WeeklyResult", image)
            if result_hit:
                self._click(context, REWARD_DISMISS, "奖励弹窗空白处")
                time.sleep(1.0)
                self._click(context, RESULT_CONTINUE, "胜利结算继续")
                time.sleep(2.0)
                log.info("周本单次流程完成")
                return True
            if self._is_map_ready(image):
                if map_stuck_since is None:
                    map_stuck_since = time.time()
                if time.time() - map_stuck_since >= MAP_STUCK_TIMEOUT:
                    self._retreat_stuck_map(context, "接近BOSS后固定等待仍未进入战斗")
                    return False
                time.sleep(0.45)
                continue
            map_stuck_since = None
            skip_hit, _ = self._recognized(context, "WeeklySkip", image)
            if skip_hit and not skip_was_visible:
                self._click(context, SKIP_BATTLE, "战斗动画跳过键")
                skip_was_visible = True
                map_stuck_since = None
                time.sleep(1.0)
                continue
            if not skip_hit:
                skip_was_visible = False
            time.sleep(0.65)
        log.warning("战斗或结算等待超时")
        return False

    def run(self, context, argv) -> bool:
        self.last_case_id = None
        self.last_run_success = False
        try:
            target_runs = self._target_runs()
            log.info("周本自定次数=%d", target_runs)
            for run_index in range(1, target_runs + 1):
                log.info("周本执行进度：%d/%d", run_index, target_runs)
                run_succeeded = False
                for attempt in range(MAX_MAP_RESTARTS + 1):
                    self._retry_requested = False
                    if self._run(context, argv):
                        run_succeeded = True
                        break
                    if not self._retry_requested or attempt >= MAX_MAP_RESTARTS:
                        return False
                    log.info("周本地图重新开始：%d/%d", attempt + 1, MAX_MAP_RESTARTS)
                if not run_succeeded:
                    return False
                if self._weekly_full:
                    log.info("周本报酬已满，提前结束剩余自定次数")
                    break
            self.last_run_success = True
            return True
        except ActionStopped:
            log.info("检测到MFA停止状态，周本立即停止且不再执行点击或滑动")
            return False

    def _run(self, context, argv) -> bool:
        log.info("周本开始：碎星虚影 / 戈里刻虚影 / 虚影宙斯")
        stop_when_full = self._stop_when_rewards_full()
        log.info("周本结束条件：%s", "600/600时结束" if stop_when_full else "仅按刷取次数执行")
        if stop_when_full and self._weekly_full:
            log.info("本次任务队列已确认周本600/600，跳过后续重复")
            return True
        page = self._navigate_to_weekly(context)
        if page is None:
            log.warning("无法接续进入周本，停止周本")
            return False
        if page == "boss_choice":
            progress = self._read_weekly_progress(context)
            if stop_when_full and progress is not None and progress[1] >= 600 and progress[0] >= progress[1]:
                self._weekly_full = True
                log.info("周本已刷满%d/%d，结束本次及后续重复", progress[0], progress[1])
                return True
            if not stop_when_full and progress is not None and progress[1] >= 600 and progress[0] >= progress[1]:
                log.info("周本已刷满%d/%d，但结束条件未勾选，继续按刷取次数执行", progress[0], progress[1])
            if not self._select_zeus(context):
                return False
            self._click(context, START_BATTLE, "开始战斗键")
            time.sleep(1.2)
            popup, _ = self._recognized(context, "WeeklyNoRewardConfirm", self._shot(context))
            if popup:
                self._click(context, NO_REWARD_CONFIRM, "奖励上限提示开启键")
                time.sleep(2.0)
            else:
                time.sleep(0.8)
        else:
            log.info("当前已经在战斗准备页，直接接续关闭第二队并开始行动")
        identified = self._prepare_and_identify(context)
        if identified is None:
            return False
        case_id, camera_done = identified
        self.last_case_id = case_id
        if not self._run_map_route(context, case_id, camera_done):
            self._retreat_stuck_map(context, "路线执行未完成")
            return False
        return self._finish_battle(context)
