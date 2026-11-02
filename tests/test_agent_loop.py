import json

import pytest

from blindspot_ci.budget import BudgetGuard
from blindspot_ci.cache import JsonCache
from blindspot_ci.experiment.agent_loop import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    BoundedAgentLoop,
    BoundedAgentTools,
    ObservationDrivenPlanner,
    ToolValidationError,
    validate_tool_args,
)
from blindspot_ci.experiment.cases import load_named_dataset
from blindspot_ci.experiment.runner import load_run
from blindspot_ci.provenance import ProvenanceLog
from blindspot_ci.providers.mock import MockVisionProvider

EXPECTED_TOOLS = {
    "list_available_tests", "select_test_case", "run_vision_inspection",
    "evaluate_predictions", "get_previous_failures", "compare_experiments",
    "request_additional_evidence", "save_regression_case", "finish_investigation",
}


def make_loop(tmp_path, planner=None, provider=None, budget=None, **kwargs):
    dataset = load_named_dataset("synthetic")
    return BoundedAgentLoop(
        provider or MockVisionProvider(), dataset, JsonCache(tmp_path / "cache"),
        ProvenanceLog(tmp_path / "prov.jsonl"),
        budget or BudgetGuard(max_calls=30, max_cost_usd=1.0), tmp_path / "runs",
        planner=planner, **kwargs)


def make_tools(tmp_path):
    dataset = load_named_dataset("synthetic")
    return BoundedAgentTools(dataset, MockVisionProvider(), JsonCache(tmp_path / "cache"),
                             BudgetGuard(max_calls=30, max_cost_usd=1.0),
                             tmp_path / "runs", "a" * 16)


class QueuePlanner:
    name = "queue-stub"

    def __init__(self, calls):
        self.calls = list(calls)

    def decide(self, state):
        return self.calls.pop(0)


def call(tool, **args):
    return {"tool": tool, "args": args}


def test_tool_inventory_has_all_nine_tools_with_closed_schemas():
    assert set(TOOL_NAMES) == EXPECTED_TOOLS
    assert len(TOOL_NAMES) == 9
    for schema in TOOL_SCHEMAS.values():
        assert schema["additionalProperties"] is False
        assert schema["type"] == "object"
    assert validate_tool_args("select_test_case", {"case_id": "normal", "reason": "baseline"}) == {
        "case_id": "normal", "reason": "baseline"}
    assert validate_tool_args("get_previous_failures", {"limit": 3}) == {"limit": 3}


@pytest.mark.parametrize("tool,args", [
    ("evaluate_predictions", {"case_id": "normal", "min_iou": 0.1}),
    ("evaluate_predictions", {}),
    ("select_test_case", {"case_id": "../bad", "reason": "x"}),
    ("select_test_case", {"case_id": "normal", "reason": "x" * 321}),
    ("get_previous_failures", {"limit": 0}),
    ("get_previous_failures", {"limit": True}),
    ("request_additional_evidence",
     {"case_id": "normal", "evidence_type": "anything", "reason": "x"}),
    ("compare_experiments", {"baseline_run_id": "not-a-run", "candidate_run_id": "a" * 16}),
    ("run_release_gate", {}),
    ("modify_score", {"case_id": "normal", "status": "PASS"}),
])
def test_tool_args_are_validated(tool, args):
    with pytest.raises(ToolValidationError):
        validate_tool_args(tool, args)


def planner_state(last_status, evidence=False):
    outcome = {"case_id": "low_light", "status": last_status, "scoreable": True,
               "iou": 0.0, "reason": "fixture"}
    return {
        "run_id": "a" * 16, "iteration": 4,
        "available_tests": [
            {"id": "alternate_view", "condition": "alternate_view", "concept": "red safety tag"},
            {"id": "absent", "condition": "absent", "concept": "red safety tag"}],
        "tested_case_ids": ["low_light"], "selected_case_id": None,
        "inspected_case_ids": ["low_light"], "evaluations": [outcome],
        "last_evaluation": outcome,
        "failures": [outcome] if last_status.startswith("FAIL") else [],
        "evidence_requested_for": ["low_light"] if evidence else [],
        "saved_regression_case_ids": [], "tools_used": ["list_available_tests"],
        "provider_requests": 1, "max_provider_requests": 8,
    }


def test_two_observation_histories_produce_different_next_actions():
    planner = ObservationDrivenPlanner()
    after_fail = planner.decide(planner_state("FAIL_FALSE_NEGATIVE"))
    after_pass = planner.decide(planner_state("PASS"))
    assert after_fail["tool"] == "request_additional_evidence"
    assert after_pass["tool"] == "select_test_case"
    assert after_fail != after_pass
    after_fail_with_evidence = planner.decide(planner_state("FAIL_FALSE_NEGATIVE", evidence=True))
    assert after_fail_with_evidence["tool"] == "select_test_case"
    assert after_fail_with_evidence["args"]["case_id"] == "alternate_view"
    assert "failed" in after_fail_with_evidence["args"]["reason"]


def test_mock_loop_is_observation_driven_and_persists_trace(tmp_path):
    report = make_loop(tmp_path).run()
    statuses = {s["case"]["id"]: s["outcome"]["status"] for s in report["steps"]}
    assert statuses == {"normal": "PASS", "low_light": "FAIL_FALSE_NEGATIVE",
                        "alternate_view": "PASS", "occluded": "UNKNOWN", "absent": "PASS"}
    tools = [entry["tool"] for entry in report["trace"]]
    fail_eval = max(i for i, entry in enumerate(report["trace"])
                    if entry["tool"] == "evaluate_predictions"
                    and entry["observation"]["case_id"] == "low_light")
    assert tools[fail_eval + 1] == "request_additional_evidence"
    assert tools[fail_eval + 2] == "select_test_case"
    assert report["trace"][fail_eval + 2]["args"]["case_id"] == "alternate_view"
    assert report["mode"] == "MOCK_FIXTURE"
    assert report["finish_reason"]
    saved = load_run(tmp_path / "runs", report["id"])
    assert saved["trace"] == report["trace"]
    assert saved["id"] == report["id"]


def test_final_summary_references_real_run_and_experiment_ids(tmp_path):
    report = make_loop(tmp_path).run()
    experiment_ids = [s["experiment_id"] for s in report["steps"]]
    assert experiment_ids and len(set(experiment_ids)) == len(experiment_ids)
    assert report["id"] in report["final_summary"]
    assert all(experiment_id in report["final_summary"] for experiment_id in experiment_ids)
    assert all(s["case"]["id"] in report["final_summary"] for s in report["steps"])


def test_max_iterations_stops_the_loop(tmp_path):
    report = make_loop(tmp_path, max_iterations=3).run()
    assert report["iterations"] == 3
    assert report["finish_reason"] == "max_iterations_reached"
    assert len(report["trace"]) == 3


def test_max_provider_requests_stops_the_loop(tmp_path):
    report = make_loop(tmp_path, max_provider_requests=1).run()
    assert report["provider_requests"] == 1
    assert len(report["steps"]) == 1
    assert "budget_or_request_cap" in report["finish_reason"]
    assert "max_provider_requests" in report["finish_reason"]


def test_budget_failure_stops_the_loop(tmp_path):
    report = make_loop(tmp_path, budget=BudgetGuard(max_calls=0, max_cost_usd=1.0)).run()
    assert report["steps"] == []
    assert "budget_or_request_cap" in report["finish_reason"]


def test_provider_failure_stops_without_a_score(tmp_path):
    class Broken(MockVisionProvider):
        def inspect(self, scenario, probe):
            raise RuntimeError("dependency down")

    report = make_loop(tmp_path, provider=Broken()).run()
    assert report["steps"] == []
    assert "provider_failure" in report["finish_reason"]


def test_user_cancellation_stops_the_loop(tmp_path):
    checks = {"count": 0}

    def should_cancel():
        checks["count"] += 1
        return checks["count"] >= 3

    report = make_loop(tmp_path, should_cancel=should_cancel).run()
    assert report["finish_reason"] == "cancelled_by_user"
    assert report["trace"][-1]["tool"] == "cancelled_by_user"


def test_repeated_identical_experiment_needs_justification(tmp_path):
    planner = QueuePlanner([
        call("select_test_case", case_id="normal", reason="first"),
        call("run_vision_inspection", case_id="normal"),
        call("evaluate_predictions", case_id="normal"),
        call("select_test_case", case_id="normal", reason="again without justification"),
        call("finish_investigation", reason="should not reach"),
    ])
    report = make_loop(tmp_path, planner=planner).run()
    assert report["provider_requests"] == 1
    assert len(report["steps"]) == 1
    assert "repeated identical experiment" in report["finish_reason"]


def test_repeat_with_justification_gets_a_new_experiment_id(tmp_path):
    planner = QueuePlanner([
        call("select_test_case", case_id="normal", reason="first"),
        call("run_vision_inspection", case_id="normal"),
        call("evaluate_predictions", case_id="normal"),
        call("select_test_case", case_id="normal", reason="rerun",
             repeat_justification="check repeatability after a fixture change"),
        call("run_vision_inspection", case_id="normal"),
        call("evaluate_predictions", case_id="normal"),
        call("finish_investigation", reason="repeatability checked"),
    ])
    report = make_loop(tmp_path, planner=planner).run()
    experiments = [entry["observation"].get("experiment_id") for entry in report["trace"]
                   if entry["tool"] == "run_vision_inspection"]
    assert len(experiments) == 2 and experiments[0] != experiments[1]
    assert report["finish_reason"] == "repeatability checked"


def _assert_no_hidden(value):
    hidden = {"ground_truth", "ground_truth_box", "bbox", "visibility", "label_provenance"}
    if isinstance(value, dict):
        assert not (set(value) & hidden)
        for item in value.values():
            _assert_no_hidden(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_hidden(item)


def test_planner_state_never_contains_hidden_labels(tmp_path):
    seen = []

    class Recording:
        name = "recording"
        inner = ObservationDrivenPlanner()

        def decide(self, state):
            seen.append(state)
            return self.inner.decide(state)

    make_loop(tmp_path, planner=Recording()).run()
    assert seen
    for state in seen:
        _assert_no_hidden(state)


def test_tools_hide_labels_and_save_regression_only_after_a_fail(tmp_path):
    tools = make_tools(tmp_path)
    listing = tools.list_available_tests()
    _assert_no_hidden(listing)
    with pytest.raises(Exception, match="only a scored FAIL"):
        tools.save_regression_case("low_light", "too early")
    tools.select_test_case("low_light", "hard case")
    tools.run_vision_inspection("low_light")
    outcome = tools.evaluate_predictions("low_light")
    assert outcome["status"] == "FAIL_FALSE_NEGATIVE"
    _assert_no_hidden(outcome)
    evidence = tools.request_additional_evidence(
        "low_light", "alternate_view", "failed in low light")
    assert evidence["alternate_case_ids"][0] == "alternate_view"
    assert tools.save_regression_case("low_light", "failed in low light")["saved"] is True


def test_compare_experiments_and_previous_failures_tools(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    def run_file(run_id, status):
        steps = [{"case": {"id": "normal"}, "outcome": {"case_id": "normal", "status": status}}]
        (runs / f"{run_id}.json").write_text(json.dumps({"id": run_id, "steps": steps}),
                                             encoding="utf-8")

    run_file("a" * 16, "PASS")
    run_file("b" * 16, "FAIL_FALSE_NEGATIVE")
    tools = make_tools(tmp_path)
    tools.runs_dir = runs
    compared = tools.compare_experiments("a" * 16, "b" * 16)
    assert compared["baseline_run_id"] == "a" * 16
    assert compared["regressions"] == ["normal"]
    failures = tools.get_previous_failures(limit=5, run_id="b" * 16)
    assert failures["failures"] == [
        {"run_id": "b" * 16, "case_id": "normal", "status": "FAIL_FALSE_NEGATIVE"}]
    with pytest.raises(ToolValidationError):
        validate_tool_args("get_previous_failures", {"limit": 99})


def test_planner_cannot_modify_scores_thresholds_or_release_gate(tmp_path):
    assert not any("release_gate" in name or "threshold" in name or name == "modify_score"
                   for name in TOOL_NAMES)
    planner = QueuePlanner([call("modify_score", case_id="normal", status="PASS")])
    report = make_loop(tmp_path, planner=planner).run()
    assert report["steps"] == []
    assert "invalid_tool_args" in report["finish_reason"]
    assert report["release_gate"] == {
        "status": "SEPARATE_FIXED_SUITE_REQUIRED",
        "agent_can_modify": False, "agent_can_skip": False}


def test_trace_is_persisted_without_credentials(tmp_path):
    planner = QueuePlanner([
        {"tool": "finish_investigation",
         "args": {"reason": "done api_key=FAKE_SECRET_123 and PLANNER_SECRET_456"}}])
    planner.api_key = "PLANNER_SECRET_456"
    report = make_loop(tmp_path, planner=planner).run()
    saved_text = (tmp_path / "runs" / f"{report['id']}.json").read_text(encoding="utf-8")
    provenance = (tmp_path / "prov.jsonl").read_text(encoding="utf-8")
    assert "FAKE_SECRET_123" not in saved_text
    assert "PLANNER_SECRET_456" not in saved_text
    assert "FAKE_SECRET_123" not in provenance
    assert "[redacted]" in saved_text
    assert report["trace"][0]["tool"] == "finish_investigation"
