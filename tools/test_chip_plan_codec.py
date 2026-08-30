# -*- coding: utf-8 -*-
"""Offline tests for deterministic, private chip plan share codes."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from chip_plan_codec import PlanCodeError, decode_plan_code, encode_plan_code  # noqa: E402


PLAN = {
    "name": "切割输出",
    "enabled": True,
    "local_path": r"E:\private",
    "rules": [{
        "main_skill": "切割",
        "main_level": 2,
        "sub_skills": [
            {"name": "暴伤", "level": 1},
            {"name": "命中", "level": 2},
            {"name": "攻击", "level": 2},
        ],
        "sub_required": 2,
    }],
}


def test_round_trip_keeps_only_filter_semantics():
    code = encode_plan_code(PLAN)
    decoded = decode_plan_code(code)
    assert code.startswith("LAA-CF1-")
    assert decoded["name"] == "切割输出"
    assert decoded["rules"][0]["sub_required"] == 2
    assert "enabled" not in decoded and "local_path" not in decoded


def test_same_semantics_produce_same_code():
    reordered = dict(PLAN)
    reordered["rules"] = [dict(PLAN["rules"][0])]
    reordered["rules"][0]["sub_skills"] = list(reversed(PLAN["rules"][0]["sub_skills"]))
    assert encode_plan_code(reordered) == encode_plan_code(PLAN)


def test_tampered_code_is_rejected():
    code = encode_plan_code(PLAN)
    changed = code[:-1] + ("A" if code[-1] != "A" else "B")
    try:
        decode_plan_code(changed)
    except PlanCodeError as exc:
        assert "校验" in str(exc) or "损坏" in str(exc)
    else:
        raise AssertionError("tampered code was accepted")


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("CHIP_PLAN_CODE_OK (%d tests)" % len(tests))
