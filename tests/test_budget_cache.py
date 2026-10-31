from pathlib import Path

import pytest

from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.cache import JsonCache


def test_budget_guard_blocks_before_call():
    guard = BudgetGuard(max_calls=1, max_cost_usd=0.1)
    guard.reserve(0.1)
    with pytest.raises(BudgetExceeded):
        guard.reserve(0.0)


def test_json_cache_round_trip(tmp_path: Path):
    cache = JsonCache(tmp_path / "cache")
    cache.put("hello", {"value": 3})
    assert cache.get("hello") == {"value": 3}
    assert cache.get("missing") is None


def test_budget_guard_is_safe_under_threads():
    import threading

    guard = BudgetGuard(max_calls=50, max_cost_usd=100.0)
    taken = []

    def work():
        for _ in range(20):
            try:
                guard.reserve(0.01)
                taken.append(1)
            except BudgetExceeded:
                pass

    threads = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert guard.calls == len(taken) == 50 and guard.exhausted()


def test_damaged_cache_file_is_a_miss(tmp_path: Path):
    cache = JsonCache(tmp_path)
    cache.put("k", {"a": 1})
    cache._path("k").write_text("{not json", encoding="utf-8")
    assert cache.get("k") is None
    cache.put("k", {"a": 2})
    assert cache.get("k") == {"a": 2}
