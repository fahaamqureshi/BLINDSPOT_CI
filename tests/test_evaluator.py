from blindspot_ci.evaluator import evaluate
from blindspot_ci.models import Detection, GroundTruthObject


def test_evaluation_separates_false_negative_and_false_positive():
    result = evaluate(
        [GroundTruthObject(label="extinguisher", severity="high")],
        [Detection(label="wet_floor", confidence=0.7, source="test")],
    )
    assert [x.label for x in result.blind_spots] == ["extinguisher"]
    assert [x.label for x in result.false_positives] == ["wet_floor"]
    assert result.weighted_risk == 4.0
