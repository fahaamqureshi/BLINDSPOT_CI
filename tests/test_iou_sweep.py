import json
import sys

import pytest

from blindspot_ci import cli
from blindspot_ci.experiment.iou_sweep import render_sweep, sweep_run


def _step(case_id, condition, truth, prediction, status):
    return {"case": {"id": case_id, "condition": condition},
            "ground_truth": {"bbox": truth},
            "prediction": {"detections": ([{"bbox": prediction}] if prediction else [])},
            "outcome": {"status": status}}


def test_sweep_035_matches_saved_and_050_flips_a_box_pair():
    run = {"min_iou": 0.35, "steps": [
        _step("normal_01", "normal", [0, 0, 10, 10], [0, 0, 10, 4], "PASS"),
        _step("low_01", "low_light", [0, 0, 10, 10], [0, 0, 10, 4], "PASS"),
    ]}
    report = sweep_run(run)
    assert report["by_bar"][0.35]["by_condition"]["normal"]["statuses"] == {"normal_01": "PASS"}
    assert report["by_bar"][0.50]["by_condition"]["normal"]["passed"] == 0
    assert report["by_bar"][0.35]["by_condition"]["low_light"]["passed"] == 1
    assert report["by_bar"][0.50]["by_condition"]["low_light"]["passed"] == 0
    assert "policy flips at min pass rate 0.90:" in render_sweep(report)


def test_steps_without_stored_boxes_are_counted():
    run = {"steps": [
        _step("with_box", "normal", [0, 0, 10, 10], [0, 0, 10, 10], "PASS"),
        _step("no_prediction", "normal", [0, 0, 10, 10], None, "FAIL_FALSE_NEGATIVE"),
        _step("absent", "absent", None, None, "PASS"),
        _step("error", "unknown", None, None, "ERROR"),
    ]}
    report = sweep_run(run)
    assert report["rescored"] == 1 and report["fixed"] == 2 and report["not_rescored"] == 1
    assert "not rescored because: unscored status (1)" in render_sweep(report)


def test_035_counts_match_saved_statuses_for_every_condition():
    run = {"steps": [
        _step("normal_pass", "normal", [0, 0, 10, 10], [0, 0, 10, 10], "PASS"),
        _step("normal_miss", "normal", [0, 0, 10, 10], None, "FAIL_FALSE_NEGATIVE"),
        _step("low_pass", "low_light", [0, 0, 10, 10], [0, 0, 10, 4], "PASS"),
        _step("low_miss", "low_light", [0, 0, 10, 10], None, "FAIL_FALSE_NEGATIVE"),
        _step("absent_pass", "absent", None, None, "PASS"),
    ]}
    saved = {}
    for step in run["steps"]:
        condition = step["case"]["condition"]
        saved.setdefault(condition, []).append(step["outcome"]["status"] == "PASS")
    report = sweep_run(run)
    cells = report["by_bar"][0.35]["by_condition"]
    assert {condition: cell["passed"] for condition, cell in cells.items()} == {
        condition: sum(statuses) for condition, statuses in saved.items()
    }


def test_cli_iou_sweep_reads_the_saved_run(tmp_path, monkeypatch, capsys):
    run_id = "a" * 16
    (tmp_path / f"{run_id}.json").write_text(json.dumps({"id": run_id, "steps": [
        _step("normal_01", "normal", [0, 0, 10, 10], [0, 0, 10, 4], "PASS")
    ]}), encoding="utf-8")
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["cli", "iou-sweep", "--run", run_id])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert "normal |" in capsys.readouterr().out
