from fastapi.testclient import TestClient

from blindspot_ci.api import app


def test_health_and_run():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    response = client.post("/api/run", json={"scenario_id": "warehouse_001"})
    assert response.status_code == 200
    assert response.json()["status"] == "needs_human_review"


def test_scenarios_listed_and_hard_negative_runs():
    client = TestClient(app)
    ids = client.get("/api/scenarios").json()
    assert "corridor_003" in ids
    body = client.post("/api/run", json={"scenario_id": "corridor_003"}).json()
    assert [x["label"] for x in body["evaluation"]["false_positives"]] == ["fire_extinguisher"]
    assert body["evaluation"]["blind_spots"] == []


def test_unknown_scenario_is_404():
    assert TestClient(app).post("/api/run", json={"scenario_id": "nope"}).status_code == 404


def test_first_screen_states_limitation():
    assert "not a safety approval" in TestClient(app).get("/").text


def test_site_pages_are_served():
    client = TestClient(app)
    for path, marker in [("/", "BLINDSPOT CI"), ("/demo", "Free demo"), ("/guide", "Record the demo"), ("/app", "What to fix")]:
        response = client.get(path)
        assert response.status_code == 200 and marker in response.text, path
    assert client.get("/site.css").headers["content-type"].startswith("text/css")


def test_foreign_host_and_cross_site_post_are_refused():
    client = TestClient(app)
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 403
    assert client.get("/health", headers={"host": "127.0.0.1:8000"}).status_code == 200
    bad = client.post("/api/runs/abcdef0123456789/audit", headers={"host": "127.0.0.1:8000", "origin": "https://evil.example"})
    assert bad.status_code == 403
    same = client.post("/api/runs/abcdef0123456789/audit", headers={"host": "127.0.0.1:8000", "origin": "http://127.0.0.1:8000"})
    assert same.status_code != 403
