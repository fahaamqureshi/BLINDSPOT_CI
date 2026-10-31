from pathlib import Path

from blindspot_ci.agent import BlindspotAgent
from blindspot_ci.cache import JsonCache
from blindspot_ci.data import load_scenarios
from blindspot_ci.provenance import ProvenanceLog
from blindspot_ci.providers.mock import MockVisionProvider


def test_mock_vertical_slice_is_reviewable_and_repeatable(tmp_path: Path):
    scenario = load_scenarios()["warehouse_001"]
    agent = BlindspotAgent(MockVisionProvider(), JsonCache(tmp_path / "cache"),
                           ProvenanceLog(tmp_path / "provenance.jsonl"), max_iterations=4)
    first = agent.run(scenario)
    second = agent.run(scenario)
    assert first.status == "needs_human_review"
    assert "fire_extinguisher" in [x.label for x in first.evaluation.blind_spots]
    assert "wet_floor" in [x.label for x in first.evaluation.false_positives]
    assert all(x.cache_hit for x in second.results)
    assert (tmp_path / "provenance.jsonl").read_text(encoding="utf-8").count("run_complete") == 2
