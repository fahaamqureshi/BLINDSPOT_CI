"""Offline exact tests for condition pass rates in a saved run."""
from __future__ import annotations

from math import comb
from typing import Any

from blindspot_ci.experiment.scoring import MIN_SLICE_FOR_CLAIM, PASS

SCORED = {PASS, "FAIL_FALSE_NEGATIVE", "FAIL_FALSE_POSITIVE", "FAIL_LOCALIZATION"}
ALPHA = 0.05


def fisher_exact_p(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p-value for [[a, b], [c, d]]."""
    cells = (a, b, c, d)
    if any(type(cell) is not int or cell < 0 for cell in cells):
        raise ValueError("Fisher table cells must be nonnegative integers")
    row_one, row_two, col_one, total = a + b, c + d, a + c, a + b + c + d
    if total == 0:
        return 1.0
    denominator = comb(total, col_one)
    observed = comb(row_one, a) * comb(row_two, col_one - a) / denominator
    lower = max(0, col_one - row_two)
    upper = min(row_one, col_one)
    probability = 0.0
    for x in range(lower, upper + 1):
        current = comb(row_one, x) * comb(row_two, col_one - x) / denominator
        if current <= observed + 1e-15:
            probability += current
    return min(1.0, probability)


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values, retaining the input names."""
    for name, value in p_values.items():
        if not 0 <= value <= 1:
            raise ValueError(f"p-value for {name} must be between 0 and 1")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    previous = 0.0
    count = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        corrected = max(previous, min(1.0, (count - rank) * value))
        adjusted[name] = corrected
        previous = corrected
    return adjusted


def analyze_run(run: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    total_passed = total_scored = 0
    for step in run.get("steps", []):
        outcome = step.get("outcome") or {}
        status = outcome.get("status")
        if status not in SCORED:
            continue
        condition = str((step.get("case") or {}).get("condition", "other"))
        cell = counts.setdefault(condition, {"passed": 0, "scored": 0})
        cell["passed"] += status == PASS
        cell["scored"] += 1
        total_passed += status == PASS
        total_scored += 1

    p_values: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for condition in sorted(counts):
        cell = counts[condition]
        rest_passed = total_passed - cell["passed"]
        rest_scored = total_scored - cell["scored"]
        p_value = fisher_exact_p(cell["passed"], cell["scored"] - cell["passed"],
                                 rest_passed, rest_scored - rest_passed)
        p_values[condition] = p_value
        rate = cell["passed"] / cell["scored"]
        rest_rate = rest_passed / rest_scored if rest_scored else None
        rows[condition] = {
            "passed": cell["passed"], "scored": cell["scored"],
            "rest_passed": rest_passed, "rest_scored": rest_scored,
            "pass_rate_difference": round(rate - rest_rate, 3) if rest_rate is not None else None,
            "p_value": p_value,
        }
    adjusted = holm_adjust(p_values)
    for condition, row in rows.items():
        row["holm_p_value"] = adjusted[condition]
        row["label"] = ("underpowered" if row["scored"] < MIN_SLICE_FOR_CLAIM else
                         "worse" if row["pass_rate_difference"] < 0 and
                         adjusted[condition] < ALPHA else "not distinguishable")
    return {"rows": rows, "min_slice_for_claim": MIN_SLICE_FOR_CLAIM, "alpha": ALPHA}


def _rate_text(passed: int, scored: int) -> str:
    return f"{passed}/{scored} ({passed / scored:.3f})" if scored else "n/a"


def render_report(report: dict[str, Any]) -> str:
    lines = ["condition | slice pass | rest pass | difference | p | Holm p | label"]
    for condition, row in report["rows"].items():
        difference = "n/a" if row["pass_rate_difference"] is None else f"{row['pass_rate_difference']:+.3f}"
        lines.append(f"{condition} | {_rate_text(row['passed'], row['scored'])} | "
                     f"{_rate_text(row['rest_passed'], row['rest_scored'])} | {difference} | "
                     f"{row['p_value']:.4f} | {row['holm_p_value']:.4f} | {row['label']}")
    lines.extend(["", "p values are about chance only, not effect size or model performance.",
                  "Frames or photos are treated as independent observations."])
    return "\n".join(lines)
