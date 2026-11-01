"""Offline sensitivity checks for the saved IoU pass threshold."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from blindspot_ci.experiment.release_gate import DEFAULT_POLICY
from blindspot_ci.experiment.scoring import box_iou, wilson_interval

DEFAULT_BARS = (0.25, 0.35, 0.50, 0.75)
SCORED_STATUSES = {"PASS", "FAIL_FALSE_NEGATIVE", "FAIL_FALSE_POSITIVE", "FAIL_LOCALIZATION"}
NOT_JUDGED_STATUSES = {"ERROR", "UNKNOWN", "NOT_SCORED"}


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
    """Rescore box-dependent outcomes and retain fixed saved outcomes at each bar."""
    if not bars or any(not 0 < bar <= 1 for bar in bars) or len(set(bars)) != len(bars):
        raise ValueError("bars must be distinct numbers greater than 0 and at most 1")
    observations: list[tuple[str, str, float | None, str]] = []
    not_rescored_reasons: defaultdict[str, int] = defaultdict(int)
    for step in run.get("steps", []):
        saved_status = str((step.get("outcome") or {}).get("status", ""))
        if saved_status not in SCORED_STATUSES:
            reason = "unscored status" if saved_status in NOT_JUDGED_STATUSES else "missing saved status"
            not_rescored_reasons[reason] += 1
            continue
        case = step.get("case") or {}
        observations.append((str(case.get("id", "")), str(case.get("condition", "other")),
                             _best_iou(step), saved_status))

    by_bar: dict[float, dict[str, Any]] = {}
    for bar in bars:
        cells: dict[str, dict[str, Any]] = defaultdict(lambda: {"passed": 0, "scored": 0,
                                                                  "statuses": {}})
        for case_id, condition, best, saved_status in observations:
            status = saved_status if best is None else ("PASS" if best >= bar else "FAIL_LOCALIZATION")
            passed = status == "PASS"
            cell = cells[condition]
            cell["passed"] += passed
            cell["scored"] += 1
            cell["statuses"][case_id] = status
            if bar == 0.35 and status != saved_status:
                raise ValueError(f"saved status does not match IoU 0.35 for {case_id}")
        for cell in cells.values():
            cell["rate"] = cell["passed"] / cell["scored"] if cell["scored"] else None
            cell["wilson_95"] = wilson_interval(cell["passed"], cell["scored"])
        by_bar[bar] = {"by_condition": dict(sorted(cells.items()))}

    conditions = sorted({condition for _, condition, _, _ in observations})
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
    return {"bars": list(bars), "by_bar": by_bar,
            "not_rescored": sum(not_rescored_reasons.values()),
            "not_rescored_reasons": dict(sorted(not_rescored_reasons.items())),
            "rescored": sum(best is not None for _, _, best, _ in observations),
            "fixed": sum(best is None for _, _, best, _ in observations),
            "flips": flips, "min_pass_rate": minimum}


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
    if report["not_rescored_reasons"]:
        reasons = ", ".join(f"{reason} ({count})"
                             for reason, count in report["not_rescored_reasons"].items())
        lines.insert(1, f"not rescored because: {reasons}")
    for condition in conditions:
        cells = [report["by_bar"][bar]["by_condition"][condition] for bar in bars]
        lines.append(condition + " | " + " | ".join(_cell_text(cell) for cell in cells))
    lines.append("policy flips at min pass rate " + f"{report['min_pass_rate']:.2f}:")
    if report["flips"]:
        for flip in report["flips"]:
            states = " -> ".join(f"{bar:.2f} {'pass' if state else 'fail'}"
                                 for bar, state in ((item["bar"], item["meets_policy"])
                                                    for item in flip["bars"]))
            lines.append(f"{flip['condition']}: {states}")
    else:
        lines.append("none")
    return "\n".join(lines)
