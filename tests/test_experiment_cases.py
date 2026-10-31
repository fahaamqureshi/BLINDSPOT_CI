import json
import shutil

import pytest

from blindspot_ci.experiment import cases
from blindspot_ci.experiment.cases import DATASETS, load_dataset, load_named_dataset, public_case


@pytest.fixture
def sandbox(tmp_path):
    shutil.copytree(DATASETS / "samples", tmp_path / "samples")
    return tmp_path


def write_manifest(folder, items):
    path = folder / "m.json"
    path.write_text(json.dumps({"dataset_id": "t", "cases": items}), encoding="utf-8")
    return path


def item(case_id="one_case", **changes):
    base = {"id": case_id, "image": "samples/normal.png", "condition": "normal", "concept": "red safety tag",
            "ground_truth": {"visibility": "visible", "bbox": [200, 125, 285, 215]}}
    base.update(changes)
    return base


def test_synthetic_dataset_loads_and_is_labeled_synthetic():
    dataset = load_named_dataset("synthetic")
    assert len(dataset.cases) == 5
    assert "NOT_VALIDATION" in dataset.kind


def test_unknown_dataset_name_is_rejected():
    with pytest.raises(ValueError):
        load_named_dataset("secret")


def test_public_case_hides_labels():
    case = load_named_dataset("synthetic").cases["normal"]
    view = public_case(case)
    assert "bbox" not in json.dumps(view) and "ground_truth" not in view
    assert view["image_url"] == "/api/cases/normal/image"


@pytest.mark.parametrize("bad", [
    {"ground_truth": {"visibility": "visible", "bbox": [0, 0, 99999, 10]}},
    {"ground_truth": {"visibility": "visible"}},
    {"ground_truth": {"visibility": "absent", "bbox": [1, 1, 5, 5]}},
    {"ground_truth": {"visibility": "maybe"}},
    {"id": "../evil"},
    {"image": "../outside.png"},
    {"image": "samples/normal.txt"},
    {"recovery_case": "ghost"},
])
def test_bad_manifests_are_rejected(sandbox, bad):
    with pytest.raises((ValueError, FileNotFoundError)):
        load_dataset(write_manifest(sandbox, [item(**bad)]), sandbox)


def test_duplicate_ids_rejected(sandbox):
    with pytest.raises(ValueError):
        load_dataset(write_manifest(sandbox, [item(), item()]), sandbox)


def test_hash_mismatch_is_rejected(sandbox):
    with pytest.raises(ValueError, match="hash"):
        load_dataset(write_manifest(sandbox, [item(image_sha256="0" * 64)]), sandbox)


def test_matching_hash_is_accepted(sandbox):
    digest = cases.sha256_file(sandbox / "samples" / "normal.png")
    assert load_dataset(write_manifest(sandbox, [item(image_sha256=digest)]), sandbox).cases


def test_image_path_stays_inside_dataset(sandbox):
    case = load_dataset(write_manifest(sandbox, [item()]), sandbox).cases["one_case"]
    assert cases.image_path(case, sandbox).is_relative_to(sandbox.resolve())


def test_true_is_not_a_box_number(sandbox):
    bad = item(ground_truth={"visibility": "visible", "bbox": [True, 125, 285, 215]})
    with pytest.raises(ValueError, match="integer box"):
        load_dataset(write_manifest(sandbox, [bad]), sandbox)


def test_unchanged_dataset_is_not_hashed_twice_but_a_changed_image_is_rechecked(sandbox, monkeypatch):
    digest = cases.sha256_file(sandbox / "samples" / "normal.png")
    manifest = write_manifest(sandbox, [item(image_sha256=digest)])
    calls = []
    real = cases.sha256_file
    monkeypatch.setattr(cases, "sha256_file", lambda p: calls.append(p) or real(p))
    load_dataset(manifest, sandbox)
    load_dataset(manifest, sandbox)
    assert len(calls) == 1
    with open(sandbox / "samples" / "normal.png", "ab") as handle:
        handle.write(b"x")  # the image changed after labeling
    with pytest.raises(ValueError, match="hash"):
        load_dataset(manifest, sandbox)
