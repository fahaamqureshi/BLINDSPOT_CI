"""Do two people label the same photos the same way? Agreement between two label files.

Needed before any label set is trusted: one annotator's boxes are an opinion until a second person
checks them. Reports visibility agreement (Cohen's kappa), box overlap on cases both call visible,
and the cases to discuss. Labels stay human; nothing here changes them.
"""
from __future__ import annotations

from typing import Any

from blindspot_ci.experiment.scoring import box_iou


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two label lists of the same non-zero length")
    observed = sum(x == y for x, y in zip(a, b)) / n
    classes = set(a) | set(b)
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in classes)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def compare_labels(first: dict[str, Any], second: dict[str, Any], min_iou: float = 0.5) -> dict[str, Any]:
    one = {c["id"]: c for c in first["cases"]}
    two = {c["id"]: c for c in second["cases"]}
    shared = sorted(set(one) & set(two))
    if not shared:
        raise ValueError("the two files share no case ids")
    vis_a = [one[i]["ground_truth"]["visibility"] for i in shared]
    vis_b = [two[i]["ground_truth"]["visibility"] for i in shared]
    ious: dict[str, float] = {}
    discuss: list[dict[str, Any]] = []
    for case_id, va, vb in zip(shared, vis_a, vis_b):
        if va != vb:
            discuss.append({"case": case_id, "why": f"visibility differs ({va} vs {vb})"})
        elif va == "visible":
            iou = box_iou(tuple(one[case_id]["ground_truth"]["bbox"]), tuple(two[case_id]["ground_truth"]["bbox"]))
            ious[case_id] = round(iou, 4)
            if iou < min_iou:
                discuss.append({"case": case_id, "why": f"boxes overlap only {iou:.2f}"})
    return {
        "cases_compared": len(shared), "only_in_first": len(set(one) - set(two)),
        "only_in_second": len(set(two) - set(one)),
        "visibility_agreement": round(sum(x == y for x, y in zip(vis_a, vis_b)) / len(shared), 4),
        "visibility_kappa": round(cohen_kappa(vis_a, vis_b), 4),
        "mean_box_iou": round(sum(ious.values()) / len(ious), 4) if ious else None,
        "annotators": [sorted({c["label_provenance"]["annotator"] for c in f["cases"]}) for f in (first, second)],
        "to_discuss": discuss,
    }
