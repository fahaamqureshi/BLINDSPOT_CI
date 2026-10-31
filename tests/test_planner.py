import json
from pathlib import Path

from blindspot_ci.agent import BlindspotAgent
from blindspot_ci.cache import JsonCache
from blindspot_ci.data import load_scenarios
from blindspot_ci.models import GroundTruthObject, Scenario
from blindspot_ci.planner import HeuristicPlanner, MusePlanner
from blindspot_ci.provenance import ProvenanceLog
from blindspot_ci.providers.mock import MockVisionProvider


def make_agent(tmp_path: Path, planner=None, **kwargs) -> BlindspotAgent:
    return BlindspotAgent(MockVisionProvider(), JsonCache(tmp_path / "cache"),
                          ProvenanceLog(tmp_path / "prov.jsonl"), planner=planner, **kwargs)


def test_heuristic_planner_ranks_high_risk_first():
    scenario = load_scenarios()["warehouse_001"]
    assert HeuristicPlanner().next_probe(scenario, [], scenario.probe_catalog) == "fire_extinguisher"


def test_iteration_limit_runs_riskiest_probes_and_reports_skipped(tmp_path):
    report = make_agent(tmp_path, max_iterations=2).run(load_scenarios()["warehouse_001"])
    assert report.probes[0] == "fire_extinguisher"
    assert len(report.probes) == 2
    assert len(report.skipped_probes) == 2
    assert any("not run" in reason for reason in report.review_reasons)


def test_planner_never_exceeds_guard_even_if_it_misbehaves(tmp_path):
    class Greedy:
        name = "greedy"
        estimated_cost_usd = 0.0

        def prepare(self, scenario):
            pass

        def next_probe(self, scenario, observed, remaining):
            return scenario.probe_catalog[0]  # repeats a probe it already used

    report = make_agent(tmp_path, planner=Greedy(), max_iterations=4).run(load_scenarios()["warehouse_001"])
    assert report.iterations == 1
    assert "planner_invalid" in (tmp_path / "prov.jsonl").read_text(encoding="utf-8")


def test_planner_may_stop_early(tmp_path):
    class Lazy:
        name = "lazy"
        estimated_cost_usd = 0.0

        def prepare(self, scenario):
            pass

        def next_probe(self, scenario, observed, remaining):
            return None

    report = make_agent(tmp_path, planner=Lazy()).run(load_scenarios()["warehouse_001"])
    assert report.iterations == 0
    assert report.status == "needs_human_review"


def test_muse_planner_orders_but_never_drops_probes(tmp_path):
    class FakeMuse:
        def recommend_probes(self, scenario):
            return ["wet_floor"]

    planner = MusePlanner(FakeMuse())
    report = make_agent(tmp_path, planner=planner).run(load_scenarios()["warehouse_001"])
    assert report.probes[0] == "wet_floor"
    assert sorted(report.probes) == sorted(load_scenarios()["warehouse_001"].probe_catalog)


def test_muse_planner_failure_falls_back_to_heuristic(tmp_path):
    class Broken:
        def recommend_probes(self, scenario):
            raise RuntimeError("api down")

    report = make_agent(tmp_path, planner=MusePlanner(Broken())).run(load_scenarios()["warehouse_001"])
    assert report.probes[0] == "fire_extinguisher"
    assert report.iterations == 4


def test_paid_planner_blocked_by_budget_falls_back(tmp_path):
    class Fake:
        def recommend_probes(self, scenario):
            return ["wet_floor"]

    report = make_agent(tmp_path, planner=MusePlanner(Fake()), budget_usd=0.0).run(
        load_scenarios()["warehouse_001"])
    assert report.planner == "heuristic"


def test_clean_scenario_can_complete(tmp_path):
    scenario = Scenario(id="clean", description="A person.", probe_catalog=["person"],
                        ground_truth=[GroundTruthObject(label="person", severity="low")])
    agent = BlindspotAgent(MockVisionProvider({"clean": {"person": {"confidence": 0.9}}}),
                           JsonCache(tmp_path / "c"), ProvenanceLog(tmp_path / "p.jsonl"))
    report = agent.run(scenario)
    assert report.status == "complete"
    assert report.review_reasons == []


def test_expected_fixtures_hold_for_every_scenario(tmp_path):
    expected = json.loads((Path(__file__).parents[1] / "fixtures" / "expected_demo.json").read_text("utf-8"))
    scenarios = load_scenarios()
    for item in expected:
        report = make_agent(tmp_path / item["scenario_id"]).run(scenarios[item["scenario_id"]])
        assert report.status == item["must_have_status"]
        assert sorted(m.label for m in report.evaluation.blind_spots) == sorted(item["must_have_blind_spots"])
        assert sorted(m.label for m in report.evaluation.false_positives) == sorted(
            item["must_have_false_positives"])


def test_mock_provider_does_not_need_ground_truth():
    scenario = Scenario(id="warehouse_001", description="x", probe_catalog=["person"], ground_truth=[])
    result = MockVisionProvider().inspect(scenario, "person")
    assert [d.label for d in result.detections] == ["person"]


def test_muse_planner_reports_what_really_happened(tmp_path):
    class Good:
        def recommend_probes(self, scenario):
            return ["wet_floor"]

    class BadJson:
        def recommend_probes(self, scenario):
            raise ValueError("planner reply was not valid JSON")

    ok = make_agent(tmp_path / "a", planner=MusePlanner(Good())).run(load_scenarios()["warehouse_001"])
    assert ok.planner_note.startswith("muse order used")
    bad = make_agent(tmp_path / "b", planner=MusePlanner(BadJson())).run(load_scenarios()["warehouse_001"])
    assert bad.planner_note.startswith("fell back to heuristic")
    assert "not valid JSON" in bad.planner_note
