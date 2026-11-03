"""Security and reliability checks: host guard, corrupt-file isolation, import limits, spend caps."""
import json
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from blindspot_ci import api
from blindspot_ci.api import app
from blindspot_ci.budget import BudgetGuard
from blindspot_ci.experiment.cases import InspectionCase, image_path
from blindspot_ci.experiment.importer import import_labeled
from blindspot_ci.experiment.reviews import add_note, load_extras
from blindspot_ci.labeler import create_app
from blindspot_ci.models import Evaluation, RunReport


def test_allowed_hosts_match_exactly_including_code_run(monkeypatch):
    monkeypatch.setenv("BLINDSPOT_ALLOWED_HOSTS", "web--blindspot-ci--abc123.code.run")
    client = TestClient(app)
    assert client.get("/health", headers={"host": "web--blindspot-ci--abc123.code.run"}).status_code == 200
    assert client.get("/health", headers={"host": "web--blindspot-ci--abc123.code.run:443"}).status_code == 200
    assert client.get("/health", headers={"host": "WEB--BLINDSPOT-CI--ABC123.CODE.RUN"}).status_code == 200
    assert client.get("/health", headers={"host": "other--blindspot-ci--xyz789.code.run"}).status_code == 403
    assert client.get("/health", headers={"host": "code.run"}).status_code == 403


def test_traversal_absolute_and_wrong_type_image_paths_are_rejected(tmp_path):
    base = tmp_path / "datasets"
    for image in ("../secret.jpg", "sub/../../secret.jpg", str(tmp_path / "secret.jpg"), "photo.gif"):
        case = InspectionCase(id="case_a", title="t", image=image, condition="normal",
                              concept="x", visibility="absent")
        with pytest.raises(ValueError):
            image_path(case, base)


def test_corrupt_extras_fall_back_and_notes_still_save(tmp_path):
    run_id = "a" * 16
    (tmp_path / f"{run_id}.json").write_text(
        json.dumps({"id": run_id, "steps": [{"case": {"id": "case_a"}}]}), encoding="utf-8")
    (tmp_path / f"{run_id}.extras.json").write_text("{corrupt", encoding="utf-8")
    assert load_extras(tmp_path, run_id) == {"reviewer_notes": [], "audit": None}
    note = add_note(tmp_path, run_id, "case_a", "check this corner", "typed")
    assert note["text"] == "check this corner"
    assert load_extras(tmp_path, run_id)["reviewer_notes"][0]["text"] == "check this corner"


def test_one_corrupt_example_does_not_break_the_examples_list(tmp_path, monkeypatch):
    real = Path(api.EXAMPLES / "a165cd6773cd433a.json").read_bytes()
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "a165cd6773cd433a.json").write_bytes(real)
    (examples / f"{'c' * 16}.json").write_text("{corrupt", encoding="utf-8")
    monkeypatch.setattr(api, "EXAMPLES", examples)
    response = TestClient(app).get("/api/examples")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == ["a165cd6773cd433a"]


def test_one_corrupt_run_does_not_break_other_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    good, bad = "a" * 16, "b" * 16
    (tmp_path / f"{good}.json").write_text(json.dumps({"id": good, "steps": []}), encoding="utf-8")
    (tmp_path / f"{bad}.json").write_text("{corrupt", encoding="utf-8")
    client = TestClient(app)
    assert client.get(f"/api/runs/{good}").status_code == 200
    assert client.get(f"/api/runs/{bad}").status_code == 404


def test_corrupt_label_file_does_not_break_the_labeler(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    Image.new("RGB", (50, 50)).save(folder / "a.jpg")
    out = tmp_path / "labels.json"
    out.write_text("{corrupt", encoding="utf-8")
    client = TestClient(create_app(folder, out, "Tester"))
    response = client.get("/api/images")
    assert response.status_code == 200 and len(response.json()["images"]) == 1


def _header_only_png(path: Path, width: int, height: int) -> Path:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    payload = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT", zlib.compress(b"\x00" * 64)) + chunk(b"IEND", b"")
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize("size", [(40000, 40000), (20000, 10000)])
def test_oversized_dimensions_are_rejected_with_a_clear_error(tmp_path, size):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    photo = _header_only_png(tmp_path / "huge.png", *size)
    item = {"id": "tray_001", "image_source": str(photo),
            "ground_truth": {"visibility": "visible", "bbox": [10, 10, 100, 100]},
            "label_provenance": {"annotator": "Tester", "labeled_at": "2026-11-01"}}
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"cases": [item]}), encoding="utf-8")
    with pytest.raises(ValueError, match="pixels"):
        import_labeled(labels, datasets)


def test_run_endpoint_charges_the_session_spend_cap(monkeypatch):
    class FakeAgent:
        def __init__(self, parent):
            self.budget = BudgetGuard(max_calls=10, max_cost_usd=1, parent=parent)

        def run(self, scenario):
            self.budget.reserve(0.04)
            return RunReport(run_id="run_fake", scenario_id=scenario.id, provider="meta",
                             status="complete", iterations=1, calls=2, estimated_cost_usd=0.04,
                             probes=["person"], results=[],
                             evaluation=Evaluation(metrics=[], blind_spots=[], false_positives=[],
                                                   weighted_risk=0.0))

    monkeypatch.setenv("BLINDSPOT_PROVIDER", "meta")
    monkeypatch.setattr(api, "build_agent", lambda *args, **kwargs: FakeAgent(kwargs["budget_parent"]))
    monkeypatch.setattr(api, "_SESSION", BudgetGuard(max_calls=100, max_cost_usd=0.05))
    client = TestClient(app)
    codes = [client.post("/api/run", json={"scenario_id": "warehouse_001"}).status_code
             for _ in range(3)]
    assert codes == [200, 429, 429]
    assert api._SESSION.cost_usd == pytest.approx(0.04)


@pytest.mark.parametrize("host", ["[broken", "localhost:bad", "localhost:99999",
                                  "user@localhost", "localhost/path", "localhost#fragment"])
def test_malformed_host_is_refused_without_server_error(host):
    response = TestClient(app, raise_server_exceptions=False).get("/health", headers={"host": host})
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["http://[broken", "https://testserver", "http://testserver/path"])
def test_malformed_or_different_scheme_origin_is_refused(origin):
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/experiment", json={}, headers={"origin": origin})
    assert response.status_code == 403


@pytest.mark.parametrize("value", [[], None, {"id": "wrong", "steps": []},
                                   {"id": "a" * 16, "steps": "broken"}])
def test_structurally_invalid_saved_run_is_refused(tmp_path, monkeypatch, value):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    (tmp_path / f"{'a' * 16}.json").write_text(json.dumps(value), encoding="utf-8")
    client = TestClient(app, raise_server_exceptions=False)
    for suffix in ("", "/release-gate", "/card"):
        assert client.get(f"/api/runs/{'a' * 16}{suffix}").status_code == 404


def test_experiment_reserves_shared_budget_before_each_intercepted_call(tmp_path, monkeypatch):
    from blindspot_ci import factory
    from blindspot_ci.providers.mock import MockVisionProvider

    calls = []

    class FakeMeta(MockVisionProvider):
        name = "meta"

        def inspect(self, scenario, probe):
            calls.append(probe)
            return super().inspect(scenario, probe)

    monkeypatch.setenv("BLINDSPOT_PROVIDER", "meta")
    monkeypatch.setenv("LIVE_API_ENABLED", "true")
    monkeypatch.setenv("MODEL_API_KEY", "fake")
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(factory, "MetaSam31Adapter", lambda *args: FakeMeta())
    monkeypatch.setattr(api, "_SESSION", BudgetGuard(max_calls=100, max_cost_usd=.005))
    client = TestClient(app)
    run = client.post("/api/experiment", json={"max_steps": 5}).json()
    assert len(calls) == api._SESSION.calls == run["calls"] == 2
    assert api._SESSION.cost_usd == pytest.approx(.005)
    assert client.post("/api/experiment", json={"max_steps": 5}).status_code == 429
