import pytest

from blindspot_ci.agent import BlindspotAgent
from blindspot_ci.cache import JsonCache
from blindspot_ci.data import build_custom_scenario, parse_truth
from blindspot_ci.provenance import ProvenanceLog
from blindspot_ci.providers.mock import MockVisionProvider


def test_parse_truth_counts_and_severity():
    items = parse_truth("person=4, bus=1:high, sign")
    assert [i.label for i in items].count("person") == 4
    assert [i.severity for i in items if i.label == "bus"] == ["high"]
    assert [i.label for i in items].count("sign") == 1


@pytest.mark.parametrize("bad", ["", "person=x", "person=2:urgent", "=3"])
def test_parse_truth_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_truth(bad)


def test_custom_scenario_scores_count_mismatch(tmp_path):
    scenario = build_custom_scenario("https://example.com/a.jpg", ["person"], "person=4")
    two_found = MockVisionProvider({"live_custom": {"person": {"confidence": 0.9}}})
    report = BlindspotAgent(two_found, JsonCache(tmp_path / "c"), ProvenanceLog(tmp_path / "p.jsonl")).run(scenario)
    assert report.evaluation.metrics[0].fn == 3  # mock returns one detection, truth says four
    assert report.status == "needs_human_review"


def test_no_probes_is_an_error():
    with pytest.raises(ValueError):
        build_custom_scenario("https://example.com/a.jpg", [], "person=1")
