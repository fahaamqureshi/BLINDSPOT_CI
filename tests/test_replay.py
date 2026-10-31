import json

import pytest

from blindspot_ci.budget import BudgetGuard
from blindspot_ci.experiment.planners import MockToolPlanner, MuseToolPlanner
from blindspot_ci.experiment.replay import ReplayError, replay_planner, scored_outcomes


def fake_run(tmp_path):
    run = {
        "id": "0123456789abcdef",
        "steps": [
            {"case": {"id": "normal", "condition": "normal"},
             "outcome": {"case_id": "normal", "status": "PASS"}},
            {"case": {"id": "low_light", "condition": "low_light"},
             "outcome": {"case_id": "low_light", "status": "FAIL_FALSE_NEGATIVE"}},
            {"case": {"id": "unknown", "condition": "angle"},
             "outcome": {"case_id": "unknown", "status": "UNKNOWN"}},
            {"case": {"id": "error", "condition": "occlusion"},
             "outcome": {"case_id": "error", "status": "ERROR"}},
            {"case": {"id": "angle", "condition": "angle"},
             "outcome": {"case_id": "angle", "status": "PASS"}},
        ],
    }
    path = tmp_path / "fake-run.json"
    path.write_text(json.dumps(run), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def test_replay_is_deterministic(tmp_path):
    run = fake_run(tmp_path)
    first = replay_planner(run, MockToolPlanner(), steps=2)
    second = replay_planner(run, MockToolPlanner(), steps=2)
    assert first == second
    assert first["order"] == ["normal", "low_light"]
    assert first["comparison"]["total_cases"] == 3


def test_unknown_and_error_cases_are_excluded(tmp_path):
    outcomes = scored_outcomes(fake_run(tmp_path))
    assert outcomes == {"normal": "PASS", "low_light": "FAIL_FALSE_NEGATIVE", "angle": "PASS"}


def test_muse_planner_is_refused(tmp_path):
    planner = MuseToolPlanner("unused", "https://example.invalid/v1", "muse-spark-1.3",
                              BudgetGuard(max_calls=1, max_cost_usd=1.0))
    with pytest.raises(ReplayError, match="zero network calls"):
        replay_planner(fake_run(tmp_path), planner, steps=1)


def test_steps_larger_than_available_cases_is_capped(tmp_path):
    result = replay_planner(fake_run(tmp_path), MockToolPlanner(), steps=99)
    assert result["comparison"]["tests_run"] == 3
    assert len(result["order"]) == 3
