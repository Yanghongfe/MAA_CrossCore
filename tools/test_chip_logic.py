# -*- coding: utf-8 -*-
"""Offline tests for chip-detail parsing and deterministic grid order."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from chip_filter_flow import (  # noqa: E402
    ChipFilterFlow,
    DETAIL_LOCK_TOGGLE,
    MAIN_SKILLS,
    SUB_SKILLS,
    VISIBLE_SLOTS,
    parse_level,
    should_lock_chip,
    validate_chip_detail,
)


def test_grid_is_six_columns_then_next_row():
    assert [item["index"] for item in VISIBLE_SLOTS] == list(range(1, 19))
    assert VISIBLE_SLOTS[0]["point"] == (169, 270)
    assert VISIBLE_SLOTS[5]["point"] == (1429, 270)
    assert VISIBLE_SLOTS[6]["point"] == (169, 520)


def test_recorded_skill_catalog_is_complete():
    assert len(MAIN_SKILLS) == 35
    assert len(set(MAIN_SKILLS)) == 35
    assert len(SUB_SKILLS) == 8
    assert len(set(SUB_SKILLS)) == 8


def test_detail_classification():
    detail = validate_chip_detail([
        ("切割", 2), ("命中", 2), ("耐久", 1), ("防御", 2),
    ])
    assert detail["main_skill"] == {"name": "切割", "level": 2}
    assert detail["sub_skills"][2] == {"name": "防御", "level": 2}


def test_invalid_main_or_level_is_rejected():
    assert validate_chip_detail([
        ("攻击", 2), ("命中", 2), ("耐久", 1), ("防御", 2),
    ]) is None
    assert validate_chip_detail([
        ("切割", 4), ("命中", 2), ("耐久", 1), ("防御", 2),
    ]) is None


def test_level_parser_and_recorded_lock_point():
    assert parse_level("等级. 2") == 2
    assert parse_level("3") == 3
    assert parse_level("等级 15") is None
    assert DETAIL_LOCK_TOGGLE == (1207, 158)


def test_saved_plan_match_logic():
    detail = validate_chip_detail([
        ("切割", 2), ("命中", 2), ("耐久", 1), ("防御", 2),
    ])
    plan = {
        "levels": {
            "1": {"mode": "unlock", "conditions": {}},
            "2": {
                "mode": "conditional",
                "conditions": {
                    "切割": {"minimum_levels": {"1": [], "2": ["攻击", "命中"], "3": []}}
                },
            },
            "3": {"mode": "lock", "conditions": {}},
        }
    }
    assert should_lock_chip(detail, plan) is True
    detail["sub_skills"][0]["level"] = 1
    assert should_lock_chip(detail, plan) is False
    detail["main_skill"]["level"] = 3
    assert should_lock_chip(detail, plan) is True


def test_remainder_slots_are_bottom_aligned_after_full_pages():
    first_page = ChipFilterFlow._remainder_slots(7)
    assert [slot["point"] for slot in first_page] == [item["point"] for item in VISIBLE_SLOTS[:7]]
    bottom_page = ChipFilterFlow._remainder_slots(475)
    assert [slot["index"] for slot in bottom_page] == list(range(469, 476))
    assert bottom_page[0]["point"] == (169, 545)
    assert bottom_page[-1]["point"] == (169, 795)


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("CHIP_LOGIC_OK (%d tests)" % len(tests))
