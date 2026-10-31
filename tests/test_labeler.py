import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from blindspot_ci.experiment.cases import load_dataset
from blindspot_ci.experiment.importer import import_labeled
from blindspot_ci.labeler import create_app


@pytest.fixture
def setup(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    Image.new("RGB", (400, 300), (180, 30, 30)).save(folder / "a.jpg")
    Image.new("RGB", (400, 300), (30, 30, 30)).save(folder / "b.png")
    (folder / "notes.txt").write_text("not a photo")
    out = tmp_path / "labels.json"
    return TestClient(create_app(folder, out, "A. Tester")), out, tmp_path


def test_lists_only_photos_and_requires_a_person(setup, tmp_path):
    client, _, _ = setup
    names = [i["name"] for i in client.get("/api/images").json()["images"]]
    assert names == ["a.jpg", "b.png"]
    with pytest.raises(ValueError):
        create_app(tmp_path / "photos", tmp_path / "x.json", "  ")


def test_traversal_and_bad_boxes_are_rejected(setup):
    client, _, _ = setup
    assert client.get("/api/image/..%2Fsecret.jpg").status_code == 404
    assert client.get("/api/image/notes.txt").status_code == 404
    base = {"name": "a.jpg", "condition": "normal", "visibility": "visible"}
    assert client.post("/api/label", json={**base, "bbox": [0, 0, 999, 10]}).status_code == 422
    assert client.post("/api/label", json={**base, "bbox": None}).status_code == 422
    assert client.post("/api/label", json={**base, "visibility": "absent", "bbox": [1, 1, 5, 5]}).status_code == 422


def test_saved_labels_import_and_load_with_person_as_annotator(setup):
    client, out, tmp_path = setup
    assert client.post("/api/label", json={"name": "a.jpg", "condition": "low_light", "visibility": "visible",
                                           "bbox": [20, 40, 120, 150]}).status_code == 200
    r = client.post("/api/label", json={"name": "b.png", "condition": "absent", "visibility": "absent"})
    assert r.json() == {"saved": "tray_b", "total": 2, "of": 2}
    data = json.loads(out.read_text())
    assert all(c["label_provenance"]["annotator"] == "A. Tester" for c in data["cases"])
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    assert import_labeled(out, datasets) == 2
    cases = load_dataset(datasets / "real_manifest.json", datasets).cases
    assert cases["tray_a"].ground_truth_box == (20, 40, 120, 150) and cases["tray_b"].visibility == "absent"
    assert client.get("/api/label/a.jpg").json()["ground_truth"]["bbox"] == [20, 40, 120, 150]
