"""Deterministic scoring. Models never grade themselves; this module is the only judge."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from blindspot_ci.experiment.cases import Box, InspectionCase

PASS = "PASS"
FALSE_NEGATIVE = "FAIL_FALSE_NEGATIVE"
FALSE_POSITIVE = "FAIL_FALSE_POSITIVE"
LOCALIZATION = "FAIL_LOCALIZATION"
UNKNOWN = "UNKNOWN"
ERROR = "ERROR"  # the test could not be run; never counted as a miss
DEFAULT_MIN_IOU = 0.35
NOTE = "PASS means the model met the stated threshold on one labeled example. It is not a safety approval."


MIN_SLICE_FOR_CLAIM = 5  # below this a slice is reported as underpowered, never as a rate


def wilson_interval(passed: int, scored: int, z: float = 1.96) -> list[float] | None:
    """95 percent Wilson score interval for a pass proportion (Brown, Cai and DasGupta 2001).

    The textbook Wald interval has erratic coverage at the small counts this tool works with.
    """
    if scored <= 0:
        return None
    p = passed / scored
    denom = 1 + z * z / scored
    center = (p + z * z / (2 * scored)) / denom
    half = z * math.sqrt(p * (1 - p) / scored + z * z / (4 * scored * scored)) / denom
    return [round(max(0.0, center - half), 3), round(min(1.0, center + half), 3)]


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    status: str
    scoreable: bool
    iou: float | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "status": self.status, "scoreable": self.scoreable,
                "iou": self.iou, "reason": self.reason}


def box_iou(a: Box, b: Box) -> float:
    """Intersection over union of two half-open boxes [x1, y1, x2, y2]."""
    if a[2] <= a[0] or a[3] <= a[1] or b[2] <= b[0] or b[3] <= b[1]:
        return 0.0
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def score_case(case: InspectionCase, boxes: list[Box], min_iou: float = DEFAULT_MIN_IOU) -> CaseOutcome:
    if case.visibility == "unknown":
        return CaseOutcome(case.id, UNKNOWN, False, None,
                           "Labeled as not determinable from this image. Not scored.")
    if case.visibility == "absent":
        if boxes:
            return CaseOutcome(case.id, FALSE_POSITIVE, True, None,
                               f"Model returned {len(boxes)} detection(s) where the label says absent.")
        return CaseOutcome(case.id, PASS, True, None, "No detection, and the label says absent.")
    if not boxes:
        return CaseOutcome(case.id, FALSE_NEGATIVE, True, 0.0, "Labeled visible but the model found nothing.")
    assert case.ground_truth_box is not None
    best = round(max(box_iou(box, case.ground_truth_box) for box in boxes), 4)
    if best < min_iou:
        return CaseOutcome(case.id, LOCALIZATION, True, best,
                           f"Best box overlap {best:.2f} is below the {min_iou:.2f} threshold.")
    return CaseOutcome(case.id, PASS, True, best, f"Best box overlap {best:.2f} meets {min_iou:.2f}.")


def summarize(outcomes: list[CaseOutcome], conditions: dict[str, str], min_iou: float) -> dict[str, Any]:
    """Counts with explicit denominators, overall and per condition."""
    def count(items: list[CaseOutcome]) -> dict[str, Any]:
        scored = [o for o in items if o.scoreable]
        passed = sum(o.status == PASS for o in scored)
        return {"tested": len(items), "scored": len(scored), "passed": passed,
                "failed": len(scored) - passed, "unknown": sum(o.status == UNKNOWN for o in items),
                "errors": sum(o.status == ERROR for o in items),
                "pass_rate": round(passed / len(scored), 3) if scored else None,
                "pass_ci95": wilson_interval(passed, len(scored)),
                "underpowered": len(scored) < MIN_SLICE_FOR_CLAIM}

    by_condition: dict[str, list[CaseOutcome]] = defaultdict(list)
    for outcome in outcomes:
        by_condition[conditions.get(outcome.case_id, "other")].append(outcome)
    return {**count(outcomes), "min_iou": min_iou,
            "by_condition": {name: count(items) for name, items in sorted(by_condition.items())},
            "failures": [o.case_id for o in outcomes if o.status.startswith("FAIL")], "note": NOTE}
