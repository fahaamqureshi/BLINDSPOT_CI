import json

import pytest
from PIL import Image

from blindspot_ci.experiment.cases import load_dataset
from blindspot_ci.experiment.importer import import_labeled


def photo(path, size=(400, 300), color=(200, 30, 30)):
    Image.new("RGB", size, color).save(path)
    return path


def labels(tmp_path, items):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"cases": items}), encoding="utf-8")
    return path


def entry(image, case_id="tray_001", **truth):
    return {"id": case_id, "image_source": str(image),
            "ground_truth": truth or {"visibility": "visible", "bbox": [10, 10, 100, 100]},
            "label_provenance": {"annotator": "Tester", "labeled_at": "2026-11-01"}}


def test_import_writes_manifest_with_hashes_and_loads(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    count = import_labeled(labels(tmp_path, [entry(photo(tmp_path / "a.png"))]), datasets)
    assert count == 1
    dataset = load_dataset(datasets / "real_manifest.json", datasets)
    assert dataset.cases["tray_001"].ground_truth_box == (10, 10, 100, 100)
    manifest = json.loads((datasets / "real_manifest.json").read_text())
    assert len(manifest["cases"][0]["image_sha256"]) == 64


def test_import_preserves_source_attribution_and_license(tmp_path):
    datasets = tmp_path / "datasets"
    item = entry(photo(tmp_path / "photo.jpg"))
    provenance = {"source_url": "https://example.invalid/photo", "license": "CC BY 4.0",
                  "attribution": "Human photographer"}
    item.update(provenance)
    import_labeled(labels(tmp_path, [item]), datasets)
    saved = json.loads((datasets / "real_manifest.json").read_text())["cases"][0]
    assert {key: saved[key] for key in provenance} == provenance


def test_large_photo_is_resized_and_box_scaled(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    big = photo(tmp_path / "big.png", size=(3200, 2400))
    item = entry(big, visibility="visible", bbox=[1600, 1200, 2400, 1800])
    import_labeled(labels(tmp_path, [item]), datasets)
    case = load_dataset(datasets / "real_manifest.json", datasets).cases["tray_001"]
    assert case.ground_truth_box == (800, 600, 1200, 900)


def test_exif_rotation_is_applied_before_boxes_are_checked(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    source = tmp_path / "phone.jpg"
    image = Image.new("RGB", (400, 300), (10, 10, 10))
    exif = Image.Exif()
    exif[274] = 6  # stored sideways; upright size is 300x400
    image.save(source, exif=exif)
    item = entry(source, visibility="visible", bbox=[10, 10, 290, 390])
    import_labeled(labels(tmp_path, [item]), datasets)
    assert load_dataset(datasets / "real_manifest.json", datasets).cases


@pytest.mark.parametrize("truth", [
    {"visibility": "visible"},
    {"visibility": "visible", "bbox": [0, 0, 9999, 9999]},
    {"visibility": "absent", "bbox": [1, 1, 5, 5]},
    {"visibility": "bogus"},
])
def test_bad_labels_are_rejected(tmp_path, truth):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    with pytest.raises(ValueError):
        import_labeled(labels(tmp_path, [entry(photo(tmp_path / "a.png"), **truth)]), datasets)


def test_missing_provenance_and_missing_photo_rejected(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    item = entry(photo(tmp_path / "a.png"))
    del item["label_provenance"]["annotator"]
    with pytest.raises(ValueError):
        import_labeled(labels(tmp_path, [item]), datasets)
    with pytest.raises(ValueError):
        import_labeled(labels(tmp_path, [entry(tmp_path / "nope.png")]), datasets)


def test_existing_import_needs_force(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    path = labels(tmp_path, [entry(photo(tmp_path / "a.png"))])
    import_labeled(path, datasets)
    with pytest.raises(FileExistsError):
        import_labeled(path, datasets)
    assert import_labeled(path, datasets, force=True) == 1


def test_open_dataset_name_uses_its_own_manifest_folder_and_type(tmp_path):
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    import_labeled(labels(tmp_path, [entry(photo(tmp_path / "a.png"))]), datasets, name="open")
    assert not (datasets / "real_manifest.json").exists()
    dataset = load_dataset(datasets / "open_manifest.json", datasets)
    assert dataset.kind == "HUMAN_LABELED_OPEN_DATA_OPEN_IMAGES_V7"
    assert (datasets / "open" / "tray_001.png").is_file()


def test_unknown_dataset_name_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        import_labeled(labels(tmp_path, [entry(photo(tmp_path / "a.png"))]), tmp_path, name="other")


def test_adjudication_keeps_original_label_and_stops_scoring(tmp_path):
    from blindspot_ci.experiment.importer import adjudicate

    datasets = tmp_path / "datasets"
    datasets.mkdir()
    import_labeled(labels(tmp_path, [entry(photo(tmp_path / "a.png"))]), datasets, name="open")
    adjudicate("tray_001", "object is a different class", "A. Reviewer", "open", datasets)
    case = load_dataset(datasets / "open_manifest.json", datasets).cases["tray_001"]
    assert case.visibility == "unknown" and case.ground_truth_box is None
    adj = case.label_provenance["adjudication"]
    assert adj["original_label"]["bbox"] == [10, 10, 100, 100] and adj["by"] == "A. Reviewer"
    with pytest.raises(ValueError):
        adjudicate("tray_001", "again", "A. Reviewer", "open", datasets)
    with pytest.raises(ValueError):
        adjudicate("tray_001", "", "", "open", datasets)
