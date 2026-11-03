from fastapi.testclient import TestClient

from blindspot_ci.api import app


def test_practice_preview_is_explicitly_offline_and_scores_actual_fixtures(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the public practice preview must not build a configured provider")

    monkeypatch.setattr("blindspot_ci.api.build_experiment", forbidden)
    monkeypatch.setenv("BLINDSPOT_PROVIDER", "meta")
    monkeypatch.setenv("LIVE_API_ENABLED", "true")
    response = TestClient(app).get("/api/practice-preview")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "MOCK_FIXTURE" and body["cost_usd"] == 0
    cases = {step["case"]["id"]: step for step in body["steps"]}
    assert cases["normal"]["outcome"]["status"] == "PASS"
    assert cases["low_light"]["outcome"]["status"] == "FAIL_FALSE_NEGATIVE"
    assert cases["occluded"]["outcome"]["status"] == "UNKNOWN"
    assert cases["alternate_view"]["outcome"]["status"] == "PASS"
    assert cases["absent"]["outcome"]["status"] == "PASS"
    assert "synthetic" in body["notice"].lower()


def test_recent_runs_reopen_created_results_and_ignore_bad_files(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    client = TestClient(app)
    first = client.post("/api/experiment", json={"max_steps": 3}).json()
    second = client.post("/api/experiment", json={"max_steps": 5}).json()
    (tmp_path / "cccccccccccccccc.json").write_text("{broken", encoding="utf-8")
    (tmp_path / "dddddddddddddddd.extras.json").write_text('{"private_note":"hidden"}', encoding="utf-8")
    response = client.get("/api/runs?limit=1")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1 and rows[0]["id"] == second["id"]
    assert rows[0]["tests"] == 5 and rows[0]["failed"] == 1
    assert client.get(f"/api/runs/{rows[0]['id']}").json()["summary"] == second["summary"]
    assert {row["id"] for row in client.get("/api/runs").json()} == {first["id"], second["id"]}
    assert "ground_truth" not in response.text and "private_note" not in response.text
    assert client.get("/api/runs?limit=999").status_code == 422


def test_malformed_reviewer_sidecar_cannot_override_scores_or_break_notes(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    client = TestClient(app, raise_server_exceptions=False)
    run = client.post("/api/experiment", json={"max_steps": 3}).json()
    sidecar = tmp_path / f"{run['id']}.extras.json"
    sidecar.write_text(json.dumps({"summary": {"failed": 0}, "mode": "LIVE_META",
                                   "reviewer_notes": "invalid", "audit": 4}), encoding="utf-8")
    reopened = client.get(f"/api/runs/{run['id']}").json()
    assert reopened["summary"] == run["summary"] and reopened["mode"] == run["mode"]
    assert reopened["reviewer_notes"] == [] and reopened["audit"] is None
    response = client.post(f"/api/runs/{run['id']}/notes",
                           json={"case_id": run["steps"][0]["case"]["id"], "text": "Human review"})
    assert response.status_code == 200
    assert client.get(f"/api/runs/{run['id']}").json()["reviewer_notes"][0]["text"] == "Human review"
