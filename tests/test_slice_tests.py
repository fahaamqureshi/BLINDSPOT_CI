import json
import sys

import pytest

from blindspot_ci import cli
from blindspot_ci.experiment.slice_tests import (
    analyze_run,
    fisher_exact_p,
    holm_adjust,
    render_report,
)


def _step(case_id, condition, status):
    return {"case": {"id": case_id, "condition": condition}, "outcome": {"status": status}}


def test_fisher_two_by_two_arithmetic():
    # [[1, 3], [3, 1]]: p = (1 + 16 + 16 + 1) / 70 = 17 / 35.
    assert fisher_exact_p(1, 3, 3, 1) == pytest.approx(17 / 35)


def test_holm_adjustment_on_small_list():
    adjusted = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.20})
    assert adjusted == {"a": pytest.approx(0.03), "b": pytest.approx(0.08), "c": pytest.approx(0.20)}


def test_underpowered_slice_is_never_worse():
    run = {"steps": [_step("tiny_1", "tiny", "PASS"), _step("tiny_2", "tiny", "PASS"),
                      *[_step(f"rest_{i}", "normal", "FAIL_LOCALIZATION") for i in range(10)]]}
    report = analyze_run(run)
    assert report["rows"]["tiny"]["label"] == "underpowered"
    assert "significant" not in render_report(report).lower()


def test_cli_slice_tests_shows_chance_and_independence_notes(tmp_path, monkeypatch, capsys):
    run_id = "b" * 16
    run = {"steps": [_step(f"low_{i}", "low_light", "PASS" if i < 6 else "FAIL_LOCALIZATION")
                      for i in range(10)] +
                     [_step(f"rest_{i}", "normal", "PASS") for i in range(10)]}
    (tmp_path / f"{run_id}.json").write_text(json.dumps(run), encoding="utf-8")
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["cli", "slice-tests", "--run", run_id])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "low_light | 6/10" in output
    assert "p values are about chance only" in output
    assert "Frames or photos are treated as independent observations." in output
