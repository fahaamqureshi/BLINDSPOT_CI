import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blindspot_ci import api, cli
from blindspot_ci.config import ConfigurationError, Settings
from blindspot_ci.experiment.cases import MANIFESTS, load_named_dataset
from blindspot_ci.experiment.scoring import score_case
from blindspot_ci.workspace import initialize


@pytest.mark.parametrize(("name", "value"), [
    ("BLINDSPOT_PROVIDER", "metaa"), ("BLINDSPOT_PLANNER", "mus"),
    ("BLINDSPOT_MIN_IOU", "nan"), ("BLINDSPOT_MIN_IOU", "inf"),
    ("BLINDSPOT_MIN_IOU", "1.1"), ("BLINDSPOT_MIN_IOU", "-0.1"),
    ("BLINDSPOT_MAX_CALLS", "no"), ("BLINDSPOT_MAX_CALLS", "-1"),
    ("BLINDSPOT_MAX_ITERATIONS", "0"), ("BLINDSPOT_BUDGET_USD", "nan"),
    ("BLINDSPOT_BUDGET_USD", "-1"), ("LIVE_API_ENABLED", "tru"),
])
def test_bad_configuration_fails_explicitly(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError, match=name):
        Settings()


def test_settings_repr_does_not_expose_credential():
    assert "private-test-value" not in repr(replace(Settings(), model_api_key="private-test-value"))


@pytest.mark.parametrize("threshold", [float("nan"), float("inf"), -1, 2])
def test_invalid_threshold_cannot_produce_a_pass(threshold):
    case = load_named_dataset("synthetic").cases["normal"]
    with pytest.raises(ValueError, match="min_iou"):
        score_case(case, [[0, 0, 1, 1]], threshold)


def test_api_configuration_error_is_actionable(monkeypatch):
    monkeypatch.setenv("BLINDSPOT_PROVIDER", "typo")
    response = TestClient(api.app).get("/api/info")
    assert response.status_code == 503
    assert "BLINDSPOT_PROVIDER" in response.json()["detail"]


def test_default_missing_dataset_is_not_an_internal_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_DATASET", "real")
    monkeypatch.setitem(MANIFESTS, "real", tmp_path / "missing.json")
    response = TestClient(api.app).post("/api/experiment", json={"max_steps": 1})
    assert response.status_code == 404


@pytest.mark.parametrize("manifest", [[], {"cases": None}, {"cases": [None]},
    {"cases": [{"id": "case", "image": "a.png", "condition": "normal", "concept": "tag",
                "ground_truth": "visible"}]}])
def test_malformed_dataset_returns_input_error(tmp_path, monkeypatch, manifest):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setitem(MANIFESTS, "real", path)
    assert TestClient(api.app).get("/api/cases?dataset=real").status_code == 422


def test_live_cli_helpers_refuse_disabled_network(monkeypatch):
    cfg = replace(Settings(), model_api_key="test-only", live_api_enabled=False)
    monkeypatch.setattr(cli, "Settings", lambda: cfg)
    monkeypatch.setattr(cli, "_raw_call", lambda *a, **k: pytest.fail("unexpected live request"))
    assert cli.diagnose() == 2
    assert cli.smoke_text() == 2
    assert cli.smoke_tools() == 2
    assert cli.smoke_sam("https://example.invalid/photo.png", None, "tag") == 2


def test_workspace_init_preserves_existing_files(tmp_path):
    root = initialize(tmp_path / "workspace")
    custom = root / "datasets" / "private-note.txt"
    custom.write_text("owner data", encoding="utf-8")
    initialize(root)
    assert custom.read_text() == "owner data"
    other = tmp_path / "not-empty"
    other.mkdir()
    (other / "owner.txt").write_text("keep")
    with pytest.raises(ValueError, match="empty directory"):
        initialize(other)
    assert (other / "owner.txt").read_text() == "keep"


def test_doctor_identifies_a_file_in_place_of_runs_directory(tmp_path, monkeypatch):
    from blindspot_ci.doctor import inspect_setup

    path = tmp_path / "runs"
    path.write_text("owner file")
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(path))
    report = inspect_setup()
    assert not report["ok"] and report["network_calls"] == 0
    assert next(row for row in report["checks"] if row["name"] == "runs")["status"] == "FAIL"
    assert path.read_text() == "owner file"


def test_mock_cli_disables_dotenv_before_configuration_import(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    env.pop("DOTENV_DISABLED", None)
    code = '''
import dotenv, sys
def forbidden(*args, **kwargs):
    raise AssertionError("dotenv must not be called")
dotenv.load_dotenv = forbidden
from blindspot_ci.cli import main
sys.argv = ["blindspot", "doctor", "--mock", "--json"]
main()
'''
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["network_calls"] == 0


def test_fresh_cli_workspace_from_another_directory(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
           "DOTENV_DISABLED": "1", "LIVE_API_ENABLED": "false"}
    for name in ("BLINDSPOT_WORKSPACE", "BLINDSPOT_RUNS_DIR", "BLINDSPOT_CACHE_DIR",
                 "BLINDSPOT_PROVENANCE_PATH", "MODEL_API_KEY"):
        env.pop(name, None)
    root = tmp_path / "developer workspace"

    def run(*args):
        return subprocess.run([sys.executable, "-m", "blindspot_ci.cli", *args],
                              env=env, cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)

    assert run("init", str(root)).returncode == 0
    result = run("--workspace", str(root), "doctor", "--mock", "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["network_calls"] == 0
    result = run("--workspace", str(root), "experiment", "--mock", "--steps", "5")
    assert result.returncode == 0, result.stderr
    reports = list((root / "artifacts/runs").glob("*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["summary"]["tested"] == 5 and report["estimated_cost_usd"] == 0
    assert (root / "artifacts/provenance.jsonl").is_file()
    result = run("--workspace", str(root), "card", "--run", report["id"])
    assert result.returncode == 0, result.stderr
    assert (root / "artifacts" / f'evaluation-card-{report["id"]}.md').is_file()
    result = run("--workspace", str(root), "experiment", "--mock", "--steps", "-1")
    assert result.returncode == 2 and "positive integer" in result.stdout
    assert len(list((root / "artifacts/runs").glob("*.json"))) == 1
