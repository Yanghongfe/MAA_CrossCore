# -*- coding: utf-8 -*-
"""Pure decision tests for arena stop, refresh, and challenge rules."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from arena_loop import (  # noqa: E402
    ACTION_CHALLENGE,
    ACTION_REFRESH,
    ACTION_RETRY_COUNTER,
    ACTION_STOP_CUSTOM_TARGET,
    ACTION_STOP_REFRESH_EMPTY,
    ACTION_STOP_SIM_EMPTY,
    REPEAT_CUSTOM,
    REPEAT_ZERO,
    ArenaLoop,
    decide_arena_action,
)


class _Hit:
    def __init__(self, hit):
        self.hit = hit


class _RecognitionContext:
    def __init__(self, hits):
        self.hits = hits

    def run_recognition(self, name, _image, pipeline_override=None):
        return _Hit(self.hits.get(name, False))


def check(expected, *, simulations, refreshes, candidate_ok, repeat=REPEAT_ZERO,
          challenged=0, target=1):
    actual = decide_arena_action(
        simulations, refreshes, candidate_ok, repeat, challenged, target
    )
    assert actual == expected, (expected, actual)


def main():
    check(ACTION_STOP_SIM_EMPTY, simulations=0, refreshes=15, candidate_ok=True)
    check(ACTION_RETRY_COUNTER, simulations=None, refreshes=15, candidate_ok=True)
    check(ACTION_CHALLENGE, simulations=3, refreshes=0, candidate_ok=True)
    check(ACTION_RETRY_COUNTER, simulations=3, refreshes=None, candidate_ok=False)
    check(ACTION_REFRESH, simulations=3, refreshes=2, candidate_ok=False)
    check(ACTION_STOP_REFRESH_EMPTY, simulations=3, refreshes=0, candidate_ok=False)
    check(
        ACTION_CHALLENGE,
        simulations=3,
        refreshes=2,
        candidate_ok=True,
        repeat=REPEAT_ZERO,
        challenged=9,
        target=1,
    )
    check(
        ACTION_STOP_CUSTOM_TARGET,
        simulations=3,
        refreshes=2,
        candidate_ok=True,
        repeat=REPEAT_CUSTOM,
        challenged=1,
        target=1,
    )
    arena = _RecognitionContext({"ArenaPageTitle": True, "ArenaDeployButton": True})
    partial = _RecognitionContext({"ArenaPageTitle": True, "ArenaDeployButton": False})
    loop = ArenaLoop()
    assert loop._is_arena_list(arena, object()) is True
    counter_only = _RecognitionContext({"ArenaReadRefresh": True})
    assert loop._is_arena_list(counter_only, object()) is False
    confirm = _RecognitionContext({"ConfirmStart": True})
    assert loop._is_arena_list(confirm, object()) is False
    print("ARENA_LOGIC_OK (11 tests)")


if __name__ == "__main__":
    main()
