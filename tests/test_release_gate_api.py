import json

from fastapi.testclient import TestClient

from blindspot_ci.api import app

RUN_ID = "a" * 16


def saved_run(mode="LIVE_META"):
    return {
        "id": RUN_ID,
        "mode": mode,
        "planner": "heuristic",
        "model": "sam-3.1",
        "started_at": "2026-01-01T00:00:00Z",
        "calls": 0,
        "estimated_cost_usd": 0.0,
        "min_iou": 0.35,
        "dataset": {"id": "test", "type": "HUMAN_LABELED_REAL_PHOTOS", "annotation_status": "person"},
        "summary": {"tested": 0, "passed": 0, "failed": 0, "unknown": 0, "errors": 0, "scored": 0,
                    "underpowered": True, "by_condition": {}},
        "steps": [],
        "errors": [],
    }


def write_run(tmp_path, run):
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    (runs / f"{RUN_ID}.json").write_text(json.dumps(run), encoding="utf-8")
    return runs


def test_release_gate_route_returns_decision_and_rejects_bad_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(write_run(tmp_path, saved_run())))
    client = TestClient(app)

    response = client.get(f"/api/runs/{RUN_ID}/release-gate")

    assert response.status_code == 200
    assert response.json()["decision"] == "NEEDS_REVIEW"
    assert client.get(f"/api/runs/{'b' * 16}/release-gate").status_code == 404
    assert client.get("/api/runs/not-a-run/release-gate").status_code == 404
    assert client.get(f"/api/runs/{RUN_ID}/release-gate", headers={"host": "evil.example"}).status_code == 403


def test_release_gate_route_marks_mock_run_demo_only(tmp_path, monkeypatch):
    run = saved_run("MOCK_FIXTURE")
    run["dataset"] = {"id": "synthetic", "type": "SYNTHETIC_DEVELOPMENT_FIXTURES_NOT_VALIDATION_DATA",
                       "annotation_status": "person"}
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(write_run(tmp_path, run)))

    response = TestClient(app).get(f"/api/runs/{RUN_ID}/release-gate")

    assert response.status_code == 200 and response.json()["decision"] == "DEMO_ONLY"


def test_card_and_app_include_release_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path / "runs"))
    client = TestClient(app)
    run_id = client.post("/api/experiment", json={"max_steps": 1}).json()["id"]

    card = client.get(f"/api/runs/{run_id}/card")
    page = client.get("/app")

    assert "Decision: DEMO_ONLY" in card.text
    assert "Human review is mandatory. GO_CANDIDATE is not a deployment approval or safety certification." in card.text
    assert page.status_code == 200 and "id:'release-gate'" in page.text and "Failing conditions" in page.text
