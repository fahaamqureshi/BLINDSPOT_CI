"""Labeled test cases. Ground truth lives here and is revealed only after scoring."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from blindspot_ci.resources import RESOURCE_ROOT

ROOT = RESOURCE_ROOT
DATASETS = ROOT / "datasets"
MANIFESTS = {"synthetic": DATASETS / "manifest.json", "real": DATASETS / "real_manifest.json",
             "generated": DATASETS / "generated_manifest.json",
             "open": DATASETS / "open_manifest.json",
             "corrupted": DATASETS / "corrupted_manifest.json",
             "hard": DATASETS / "hard_manifest.json",
             "video": DATASETS / "video_manifest.json",
             "coco": DATASETS / "coco_manifest.json"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
VISIBILITIES = {"visible", "absent", "unknown"}
CASE_ID = re.compile(r"^[A-Za-z0-9_-]{3,60}$")

Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class InspectionCase:
    id: str
    title: str
    image: str  # path relative to datasets/
    condition: str
    concept: str
    visibility: str  # visible | absent | unknown
    ground_truth_box: Box | None = None  # half-open pixel box [x1, y1, x2, y2]
    recovery_case: str | None = None
    note: str = ""
    label_provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Dataset:
    id: str
    kind: str
    annotation_status: str
    cases: dict[str, InspectionCase]


def image_path(case: InspectionCase, base: Path = DATASETS) -> Path:
    """Resolve a case image inside the dataset folder only."""
    root = base.resolve()
    path = (root / case.image).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"unsafe or unsupported image path for case {case.id}")
    return path


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.width, image.height


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_case(item: dict[str, Any]) -> InspectionCase:
    truth = item["ground_truth"]
    box = tuple(truth["bbox"]) if truth.get("bbox") else None
    return InspectionCase(
        id=item["id"], title=item.get("title", item["id"]), image=item["image"],
        condition=item["condition"], concept=item["concept"], visibility=truth["visibility"],
        ground_truth_box=box, recovery_case=item.get("recovery_case"), note=item.get("note", ""),
        label_provenance=item.get("label_provenance", {}),
    )


def _validate(case: InspectionCase, base: Path) -> None:
    if not CASE_ID.match(case.id):
        raise ValueError(f"unsafe case id: {case.id!r}")
    if case.visibility not in VISIBILITIES:
        raise ValueError(f"{case.id}: visibility must be one of {sorted(VISIBILITIES)}")
    path = image_path(case, base)
    if not path.is_file():
        raise FileNotFoundError(path)
    box = case.ground_truth_box
    if case.visibility == "visible":
        width, height = image_size(path)
        if box is None or len(box) != 4 or not all(isinstance(v, int) and not isinstance(v, bool) for v in box):
            raise ValueError(f"{case.id}: a visible case needs an integer box [x1, y1, x2, y2]")
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError(f"{case.id}: box {list(box)} is outside the {width}x{height} image")
    elif box is not None:
        raise ValueError(f"{case.id}: only visible cases may have a box")


_DATASET_CACHE: dict[tuple[Path, Path], tuple[tuple, Dataset]] = {}


def _signature(manifest: Path, base: Path, parsed: list[InspectionCase]) -> tuple | None:
    """Cheap fingerprint (file sizes and times) so unchanged datasets are not re-hashed on every request."""
    try:
        stats = [manifest.stat()] + [image_path(c, base).stat() for c in parsed]
    except (OSError, ValueError):
        return None  # let validation below report the real problem
    return tuple((s.st_mtime_ns, s.st_size) for s in stats)


def load_dataset(manifest: Path, base: Path = DATASETS) -> Dataset:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    items = [(item, _parse_case(item)) for item in data["cases"]]
    signature = _signature(manifest, base, [case for _, case in items])
    cached = _DATASET_CACHE.get((manifest.resolve(), base.resolve()))
    if signature is not None and cached is not None and cached[0] == signature:
        return cached[1]
    cases: dict[str, InspectionCase] = {}
    for item, case in items:
        if case.id in cases:
            raise ValueError(f"duplicate case id: {case.id}")
        _validate(case, base)
        stored = item.get("image_sha256")
        if stored and stored != sha256_file(image_path(case, base)):
            raise ValueError(f"{case.id}: image file changed since it was labeled (hash mismatch)")
        cases[case.id] = case
    for case in cases.values():
        if case.recovery_case and case.recovery_case not in cases:
            raise ValueError(f"{case.id}: unknown recovery case {case.recovery_case}")
    dataset = Dataset(data.get("dataset_id", manifest.stem), data.get("type", "UNSPECIFIED"),
                      data.get("annotation_status", "unspecified"), cases)
    if signature is not None:
        _DATASET_CACHE[(manifest.resolve(), base.resolve())] = (signature, dataset)
    return dataset


def load_named_dataset(name: str) -> Dataset:
    if name not in MANIFESTS:
        raise ValueError("dataset must be 'synthetic', 'real', 'open', 'hard', 'video', 'coco', 'generated' or 'corrupted'")
    if not MANIFESTS[name].is_file():
        raise FileNotFoundError(f"no {name} manifest at {MANIFESTS[name]}. See docs/dataset.md")
    return load_dataset(MANIFESTS[name])


def public_case(case: InspectionCase, base: Path = DATASETS) -> dict[str, Any]:
    """What the planner and the browser may see before a test runs: no labels."""
    width, height = image_size(image_path(case, base))
    return {"id": case.id, "title": case.title, "condition": case.condition, "concept": case.concept,
            "image_url": f"/api/cases/{case.id}/image", "width": width, "height": height,
            "note": case.note}
