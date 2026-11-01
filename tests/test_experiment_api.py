import pytest
from fastapi.testclient import TestClient

from blindspot_ci.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.delenv("LIVE_API_ENABLED", raising=False)
    return TestClient(app)


def test_cases_listing_hides_every_label(client):
    body = client.get("/api/cases").text
    assert "normal" in body and "bbox" not in body and "ground_truth" not in body


def test_case_image_served_and_traversal_blocked(client):
    ok = client.get("/api/cases/normal/image")
    assert ok.status_code == 200 and ok.headers["content-type"].startswith("image/")
    assert client.get("/api/cases/ghost/image").status_code == 404
    assert client.get("/api/cases/..%2F..%2Fpyproject.toml/image").status_code in (404, 422)


def test_experiment_endpoint_and_run_lookup(client):
    report = client.post("/api/experiment", json={"max_steps": 2}).json()
    assert report["mode"] == "MOCK_FIXTURE" and len(report["steps"]) == 2
    assert client.get(f"/api/runs/{report['id']}").json()["id"] == report["id"]
    assert client.get("/api/runs/not-a-run").status_code in (400, 404)


def test_experiment_step_bounds(client):
    assert client.post("/api/experiment", json={"max_steps": 0}).status_code == 422
    assert client.post("/api/experiment", json={"max_steps": 99}).status_code == 422


def test_live_run_is_refused_without_switch(client, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_PROVIDER", "meta")
    monkeypatch.setenv("MODEL_API_KEY", "LLM_a_b")
    assert client.post("/api/experiment", json={"max_steps": 1}).status_code == 403


def test_probe_page_redirects_home(client):
    response = client.get("/probes", follow_redirects=False)
    assert response.status_code == 307 and response.headers["location"] == "/"
