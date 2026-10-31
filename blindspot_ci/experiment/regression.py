"""Regression gate: did the candidate run get worse than the baseline on the same cases?

Two runs on the same labeled cases are paired. A case that passed before and fails now is a regression, the
reverse is a fix. The exact sign test (McNemar's exact form) asks whether the regressions outnumber the fixes
by more than chance. The gate fails on any significant drop. It never reads a label or calls a model.
"""
from __future__ import annotations

from math import comb
from typing import Any

SCORED = {"PASS", "FAIL_FALSE_NEGATIVE", "FAIL_FALSE_POSITIVE", "FAIL_LOCALIZATION"}


def sign_test_p(worse: int, better: int) -> float:
    """Two-sided exact binomial p-value for worse versus better, under no real change."""
    n = worse + better
    if n == 0:
        return 1.0
    k = min(worse, better)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def compare_runs(baseline: dict[str, Any], candidate: dict[str, Any], alpha: float = 0.05) -> dict[str, Any]:
    def status(run: dict[str, Any]) -> dict[str, str]:
        return {s["case"]["id"]: s["outcome"]["status"] for s in run["steps"]}

    before, after = status(baseline), status(candidate)
    shared = sorted(c for c in set(before) & set(after) if before[c] in SCORED and after[c] in SCORED)
    if not shared:
        raise ValueError("the runs share no scored cases")
    regressions = [c for c in shared if before[c] == "PASS" and after[c] != "PASS"]
    fixes = [c for c in shared if before[c] != "PASS" and after[c] == "PASS"]
    p = sign_test_p(len(regressions), len(fixes))
    significant = p < alpha and len(regressions) > len(fixes)
    return {
        "cases_compared": len(shared), "baseline_passed": sum(before[c] == "PASS" for c in shared),
        "candidate_passed": sum(after[c] == "PASS" for c in shared),
        "regressions": regressions, "fixes": fixes, "p_value": round(p, 4),
        "verdict": "FAIL: significant regression" if significant else
                   ("WARN: some cases regressed" if regressions else "OK: no regression"),
        "note": "Only cases scored in both runs are paired. Small samples rarely reach significance, so read the case lists.",
    }
