import io
import json
import sys
from dataclasses import replace

import pytest

from blindspot_ci import cli
from blindspot_ci.config import Settings


def _no_key():
    return replace(Settings(), model_api_key=None)


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["blindspot", *argv])
    cli.main()


def test_demo_prints_a_report(monkeypatch, capsys):
    run_cli(monkeypatch, "demo")
    report = json.loads(capsys.readouterr().out)
    assert report["scenario_id"] == "warehouse_001"
    assert report["status"] == "needs_human_review"


def test_run_fixture_each_scenario(monkeypatch, capsys):
    for scenario in ("warehouse_001", "lab_002", "corridor_003"):
        run_cli(monkeypatch, "run-fixture", "--scenario", scenario)
        assert json.loads(capsys.readouterr().out)["scenario_id"] == scenario


def test_unknown_scenario_exits_with_message(monkeypatch):
    with pytest.raises(SystemExit) as info:
        run_cli(monkeypatch, "run-fixture", "--scenario", "nope")
    assert "unknown scenario" in str(info.value)


def test_live_commands_need_a_key(monkeypatch, capsys):
    monkeypatch.setattr(cli, "Settings", _no_key)
    for argv in (["smoke-meta"], ["diagnose"]):
        with pytest.raises(SystemExit) as info:
            run_cli(monkeypatch, *argv)
        assert info.value.code == 2
    assert "MODEL_API_KEY is not set" in capsys.readouterr().out


def test_smoke_tools_needs_a_key(monkeypatch, capsys):
    from blindspot_ci import cli

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(cli, "Settings", lambda: type("S", (), {"model_api_key": None})())
    assert cli.smoke_tools() == 2
    assert "MODEL_API_KEY" in capsys.readouterr().out


def test_smoke_tools_reports_a_planner_failure(monkeypatch, capsys):
    from blindspot_ci import cli
    from blindspot_ci.experiment import planners

    class Cfg:
        live_api_enabled = True
        model_api_key = "LLM_a_b"
        meta_base_url = "https://example.invalid/v1"
        text_model = "muse-spark-1.3"

    def refuse(self, cases, remaining, history):
        raise planners.PlannerError("no tool call")

    monkeypatch.setattr(cli, "Settings", Cfg)
    monkeypatch.setattr(planners.MuseToolPlanner, "choose", refuse)
    assert cli.smoke_tools() == 1
    assert "failed" in capsys.readouterr().out


def test_diagnose_replaces_unencodable_reply(monkeypatch):
    class Cfg:
        live_api_enabled = True
        model_api_key = "LLM_test_key"
        meta_base_url = "https://example.invalid/v1"

    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="cp1252")
    monkeypatch.setattr(cli, "Settings", Cfg)
    monkeypatch.setattr(cli, "_raw_call", lambda *args, **kwargs: "reply \U00002728")
    monkeypatch.setattr(sys, "stdout", stream)
    assert cli.diagnose() == 0
    stream.flush()
    assert "reply ?" in output.getvalue().decode("cp1252")
