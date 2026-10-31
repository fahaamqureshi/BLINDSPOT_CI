"""Is the agent's choice of tests better than chance at finding failures?

Active testing (Kossen et al., ICML 2021) treats test selection as a decision with a cost. Here the
question is simple and checkable: given every case's outcome, how many failures did the agent's first
k tests find, compared with k tests drawn at random? The comparison is exact (hypergeometric), not
simulated, and it needs every case scored once, which the cache makes cheap.
"""
from __future__ import annotations

from math import comb
from typing import Any


def compare_to_random(agent_failed: list[bool], total_cases: int, total_failures: int) -> dict[str, Any]:
    """agent_failed[i] is True when the agent's i-th test failed. total_* cover the whole dataset."""
    k, n, f = len(agent_failed), total_cases, total_failures
    if not 0 < k <= n or not 0 <= f <= n:
        raise ValueError("need 0 < tests run <= total cases and 0 <= failures <= total cases")
    found = sum(agent_failed)
    if found > f:
        raise ValueError("the agent cannot find more failures than exist")
    denom = comb(n, k)
    tail = sum(comb(f, i) * comb(n - f, k - i) for i in range(found, min(f, k) + 1)) / denom
    first = next((i + 1 for i, failed in enumerate(agent_failed) if failed), None)
    return {
        "tests_run": k, "total_cases": n, "total_failures": f, "agent_failures_found": found,
        "random_expected_found": round(k * f / n, 3),
        "p_random_finds_at_least_as_many": round(tail, 4),
        "agent_first_failure_at": first,
        "random_expected_first_failure_at": round((n + 1) / (f + 1), 2) if f else None,
        "note": ("With few cases this cannot separate skill from luck. "
                 "A small p value is suggestive, a large one is uninformative."),
    }
