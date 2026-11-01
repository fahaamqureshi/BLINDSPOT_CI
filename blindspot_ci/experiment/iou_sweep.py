"""Offline sensitivity checks for the saved IoU pass threshold."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from blindspot_ci.experiment.release_gate import DEFAULT_POLICY
from blindspot_ci.experiment.scoring import box_iou, wilson_interval

DEFAULT_BARS = (0.25, 0.35, 0.50, 0.75)


def _box(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        return None
    return tuple(value)  # type: ignore[return-value]


def _prediction_boxes(step: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    detections = (step.get("prediction") or {}).get("detections") or []
    return [box for detection in detections if (box := _box(detection.get("bbox"))) is not None]


def _best_iou(step: dict[str, Any]) -> float | None:
    truth = _box((step.get("ground_truth") or {}).get("bbox"))
    boxes = _prediction_boxes(step)
    if truth is None or not boxes:
        return None
    return max(box_iou(truth, box) for box in boxes)


def sweep_run(run: dict[str, Any], bars: tuple[float, ...] = DEFAULT_BARS) -> dict[str, Any]:
    """Rescore stored visible box pairs at each requested threshold."""
    if not bars or any(not 0 < bar <= 1 for bar in bars) or len(set(bars)) != len(bars):
        raise ValueError("bars must be distinct numbers greater than 0 and at most 1")
    eligible: list[tuple[str, str, float, str]] = []
    not_rescored = 0
    for step in run.get("steps", []):
        best = _best_iou(step)
        if best is None:
            not_rescored += 1
            continue
        case = step.get("case") or {}
        eligible.append((str(case.get("id", "")), str(case.get("condition", "other")), best,
                         str((step.get("outcome") or {}).get("status", ""))))

    by_bar: dict[float, dict[str, Any]] = {}
    for bar in bars:
        cells: dict[str, dict[str, Any]] = defaultdict(lambda: {"passed": 0, "scored": 0,
                                                                  "statuses": {}})
        for case_id, condition, best, saved_status in eligible:
            passed = best >= bar
            cell = cells[condition]
            cell["passed"] += passed
            cell["scored"] += 1
            cell["statuses"][case_id] = "PASS" if passed else "FAIL_LOCALIZATION"
            if bar == 0.35 and (saved_status == "PASS") != passed:
                raise ValueError(f"saved status does not match IoU 0.35 for {case_id}")
        for cell in cells.values():
            cell["rate"] = cell["passed"] / cell["scored"] if cell["scored"] else None
            cell["wilson_95"] = wilson_interval(cell["passed"], cell["scored"])
        by_bar[bar] = {"by_condition": dict(sorted(cells.items()))}

    conditions = sorted({condition for _, condition, _, _ in eligible})
    flips = []
    minimum = DEFAULT_POLICY["min_pass_rate"]
    for condition in conditions:
        states = []
        for bar in bars:
            cell = by_bar[bar]["by_condition"].get(condition, {"rate": None})
            rate = cell["rate"]
            states.append((bar, rate is not None and rate >= minimum))
        if len({state for _, state in states}) > 1:
            flips.append({"condition": condition,
                          "bars": [{"bar": bar, "meets_policy": state} for bar, state in states]})
    return {"bars": list(bars), "by_bar": by_bar, "not_rescored": not_rescored,
            "rescored": len(eligible), "flips": flips, "min_pass_rate": minimum}


def _cell_text(cell: dict[str, Any]) -> str:
    interval = cell["wilson_95"]
    shown_interval = "n/a" if interval is None else f"[{interval[0]:.3f}, {interval[1]:.3f}]"
    return f"{cell['passed']}/{cell['scored']} {shown_interval}"


def render_sweep(report: dict[str, Any]) -> str:
    bars = report["bars"]
    conditions = sorted({condition for data in report["by_bar"].values()
                         for condition in data["by_condition"]})
    lines = [f"not rescored: {report['not_rescored']}",
             f"rescored: {report['rescored']}",
             "condition | " + " | ".join(f"bar {bar:.2f}" for bar in bars)]
    for condition in conditions:
        cells = [report["by_bar"][bar]["by_condition"][condition] for bar in bars]
        lines.append(condition + " | " + " | ".join(_cell_text(cell) for cell in cells))
    if report["flips"]:
        lines.append("policy flips at min pass rate " + f"{report['min_pass_rate']:.2f}:")
        for flip in report["flips"]:
            states = " -> ".join(f"{bar:.2f} {'pass' if state else 'fail'}"
                                 for bar, state in ((item["bar"], item["meets_policy"])
                                                    for item in flip["bars"]))
            lines.append(f"{flip['condition']}: {states}")
    return "\n".join(lines)
