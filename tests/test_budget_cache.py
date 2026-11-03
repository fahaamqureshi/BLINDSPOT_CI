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


def test_concurrent_run_budgets_share_atomic_parent_cap():
    from concurrent.futures import ThreadPoolExecutor

    parent = BudgetGuard(max_calls=100, max_cost_usd=0.05)
    children = [BudgetGuard(max_calls=10, max_cost_usd=1, parent=parent) for _ in range(20)]

    def reserve(child):
        try:
            child.reserve(0.01)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, children))
    assert sum(results) == parent.calls == 5
    assert parent.cost_usd == pytest.approx(0.05)
    assert sum(child.calls for child in children) == 5
    assert sum(child.cost_usd for child in children) == pytest.approx(parent.cost_usd)


def test_refused_child_reservation_releases_parent_cost_only():
    parent = BudgetGuard(max_calls=3, max_cost_usd=0.05)
    child = BudgetGuard(max_calls=2, max_cost_usd=0.05, parent=parent)
    child.reserve(0.04)
    child.release_cost(0.04)
    assert child.cost_usd == parent.cost_usd == 0
    assert child.calls == parent.calls == 1


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf")])
def test_invalid_reservation_cannot_reduce_or_bypass_cap(amount):
    guard = BudgetGuard(max_calls=10, max_cost_usd=1)
    with pytest.raises(ValueError):
        guard.reserve(amount)
    assert guard.calls == 0 and guard.cost_usd == 0


def test_refund_cannot_release_other_children_reservations():
    parent = BudgetGuard(max_calls=10, max_cost_usd=1)
    first = BudgetGuard(max_calls=5, max_cost_usd=1, parent=parent)
    second = BudgetGuard(max_calls=5, max_cost_usd=1, parent=parent)
    first.reserve(.1)
    second.reserve(.2)
    first.release_cost(10)
    assert parent.cost_usd == pytest.approx(.2)
