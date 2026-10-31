from fastapi.testclient import TestClient

from blindspot_ci.api import app

COCO, DAVIS = "a165cd6773cd433a", "8f6003378706480a"


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path / "no_runs"))
    return TestClient(app)


def test_examples_list_both_saved_runs_without_local_artifacts(tmp_path, monkeypatch):
    rows = {r["id"]: r for r in client(tmp_path, monkeypatch).get("/api/examples").json()}

    assert set(rows) == {COCO, DAVIS}
    assert rows[COCO]["decision"] == "NO_GO" and rows[COCO]["tests"] == 132 and rows[COCO]["scored"] == 132
    assert "low_light 6 of 10" in rows[COCO]["headline"] and "0.90 bar" in rows[COCO]["headline"]
    assert rows[DAVIS]["decision"] == "NEEDS_REVIEW" and rows[DAVIS]["tests"] == 112
    assert set(rows[COCO]) == {"id", "title", "dataset", "mode", "decision", "headline", "passed", "scored",
                               "cost_usd", "tests"}


def test_example_runs_open_through_run_card_and_gate(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)

    assert c.get(f"/api/runs/{COCO}/release-gate").json()["decision"] == "NO_GO"
    assert c.get(f"/api/runs/{DAVIS}/release-gate").json()["decision"] == "NEEDS_REVIEW"
    assert c.get(f"/api/runs/{COCO}").json()["id"] == COCO
    assert "Decision: NO_GO" in c.get(f"/api/runs/{COCO}/card").text


def test_unknown_and_malformed_run_ids_are_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)

    assert c.get(f"/api/runs/{'c' * 16}/release-gate").status_code == 404
    assert c.get(f"/api/runs/{'c' * 16}").status_code == 404
    assert c.get("/api/runs/..%2f..%2fetc/release-gate").status_code == 404
    assert c.get("/api/runs/not-a-run").status_code == 404


def test_missing_photo_answers_404_with_message(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    case_id = c.get("/api/cases").json()["cases"][0]["id"]
    monkeypatch.setattr("blindspot_ci.api.image_path", lambda case: tmp_path / "absent.png")

    response = c.get(f"/api/cases/{case_id}/image")

    assert response.status_code == 404 and "not in this checkout" in response.json()["detail"]
