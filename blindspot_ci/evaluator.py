from __future__ import annotations

from blindspot_ci.models import ClassMetric, Detection, Evaluation, GroundTruthObject

_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 4.0}


def _metric(label: str, gt: list[GroundTruthObject], detections: list[Detection]) -> ClassMetric:
    expected = [item for item in gt if item.label == label]
    actual = [item for item in detections if item.label == label]
    tp = min(len(expected), len(actual))
    fn = len(expected) - tp
    fp = len(actual) - tp
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    severity = expected[0].severity if expected else "low"
    return ClassMetric(label=label, tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1, severity=severity)


def evaluate(gt: list[GroundTruthObject], detections: list[Detection]) -> Evaluation:
    labels = sorted({x.label for x in gt} | {x.label for x in detections})
    metrics = [_metric(label, gt, detections) for label in labels]
    blind_spots = [metric for metric in metrics if metric.fn > 0]
    false_positives = [metric for metric in metrics if metric.fp > 0]
    weighted_risk = sum(metric.fn * _WEIGHT.get(metric.severity, 1.0) for metric in metrics)
    return Evaluation(metrics=metrics, blind_spots=blind_spots, false_positives=false_positives, weighted_risk=weighted_risk)
