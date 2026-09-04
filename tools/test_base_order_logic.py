# -*- coding: utf-8 -*-
"""Offline tests for base-order recognition and decisions; sends no input."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from base_order_domain import (  # noqa: E402
    choose_order_action,
    is_order_eligible,
    order_kind,
    order_signature,
    parse_order_cost,
)


def test_order_types_and_costs():
    assert order_kind("普通构建订单 稀有黑匣 X18") == "build"
    assert order_kind("稀有星币订单 IV") == "coin"
    assert order_kind("稀有技术点订单") == "tech"
    assert parse_order_cost("奖励X2 稀有黑匣 X18 可交付") == 18


def test_friend_signature_ignores_reward_level():
    first = {"kind": "build", "rare": False, "cost": 18}
    second = {"kind": "build", "rare": False, "cost": 18}
    assert order_signature(first) == "build:normal:18"
    assert order_signature(first) == order_signature(second)


def test_default_build_and_rare_filters():
    settings = {
        "build_costs": {6, 8, 16}, "rare_coin": False, "rare_tech": True,
    }
    build = {"kind": "build", "cost": 8, "rare": False, "signature": "build:normal:8"}
    coin = {"kind": "coin", "cost": 10, "rare": True, "signature": "coin:rare:10"}
    tech = {"kind": "tech", "cost": 10, "rare": True, "signature": "tech:rare:10"}
    assert is_order_eligible(build, settings)
    assert not is_order_eligible(coin, settings)
    assert is_order_eligible(tech, settings)
    assert not is_order_eligible(tech, settings, {"tech:rare:10"}, friend=True)
    assert is_order_eligible(tech, settings, {"tech:rare:10"}, friend=False)


def test_action_prefers_available_then_exact_shortage_candidate_order():
    settings = {"build_costs": {8}, "build_synth": True}
    short = {
        "kind": "build", "cost": 8, "rare": False,
        "signature": "build:normal:8", "available": False, "short_material": True,
    }
    ready = dict(short, signature="build:normal:8-ready", available=True)
    assert choose_order_action([ready], settings)[0] == "submit"
    assert choose_order_action([short], settings)[0] == "synthesize"
    assert choose_order_action([short], settings, {"build:normal:8"}) == (
        "library_done", None
    )


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("BASE_ORDER_LOGIC_OK (%d tests)" % len(tests))
