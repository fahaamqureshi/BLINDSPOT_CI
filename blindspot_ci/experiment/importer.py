"""Import human-labeled photos. Labels come from a person, never from Muse or SAM."""
from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from blindspot_ci.experiment.cases import (
    CASE_ID,
    DATASETS,
    IMAGE_SUFFIXES,
    VISIBILITIES,
    sha256_file,
)
from blindspot_ci.fsutil import atomic_write_text
from blindspot_ci.media import MAX_IMAGE_BYTES

MAX_EDGE = 1600
MAX_IMAGE_PIXELS = 50_000_000  # decoded-size bound, checked from the header before pixels load
REQUIRED_PROVENANCE = ("annotator", "labeled_at")


def _normalized(source: Path) -> tuple[Image.Image, tuple[int, int]]:
    """Upright (EXIF applied) and resized so the long edge is at most MAX_EDGE.

    People label the photo as they see it, upright. Phone files often store it rotated plus an
    EXIF flag, so the pixels must be rotated before boxes are checked or sent to the model.
    """
    try:
        with Image.open(source) as raw:
            width, height = raw.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(f"{source.name}: image is {width}x{height} "
                                 f"({width * height:,} pixels); the limit here is "
                                 f"{MAX_IMAGE_PIXELS:,} pixels. Resize it first")
            raw.load()
            upright = ImageOps.exif_transpose(raw)
    except Image.DecompressionBombError as exc:
        raise ValueError(f"{source.name}: image has too many pixels to import safely. "
                         f"Resize it first") from exc
    original = upright.size
    scale = min(1.0, MAX_EDGE / max(original))
    if scale < 1.0:
        upright = upright.resize((round(original[0] * scale), round(original[1] * scale)), Image.LANCZOS)
    return upright, original


def _scaled_box(box: list[int], original: tuple[int, int], new: tuple[int, int]) -> list[int]:
    sx, sy = new[0] / original[0], new[1] / original[1]
    x1, y1 = math.floor(box[0] * sx), math.floor(box[1] * sy)
    x2, y2 = math.ceil(box[2] * sx), math.ceil(box[3] * sy)
    return [max(0, x1), max(0, y1), min(new[0], x2), min(new[1], y2)]


def _check_label(case: dict[str, Any], original: tuple[int, int]) -> None:
    case_id = case["id"]
    truth = case["ground_truth"]
    if truth["visibility"] not in VISIBILITIES:
        raise ValueError(f"{case_id}: visibility must be one of {sorted(VISIBILITIES)}")
    box = truth.get("bbox")
    if truth["visibility"] == "visible":
        if not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, int) and not isinstance(v, bool) for v in box):
            raise ValueError(f"{case_id}: a visible case needs an integer box [x1, y1, x2, y2]")
        if not (0 <= box[0] < box[2] <= original[0] and 0 <= box[1] < box[3] <= original[1]):
            raise ValueError(f"{case_id}: box {box} is outside the upright {original[0]}x{original[1]} image")
    elif box is not None:
        raise ValueError(f"{case_id}: only visible cases may have a box")
    provenance = case.get("label_provenance", {})
    missing = [k for k in REQUIRED_PROVENANCE if not provenance.get(k)]
    if missing:
        raise ValueError(f"{case_id}: label_provenance needs {', '.join(missing)}")


KINDS = {
    "real": ("real-user-local", "HUMAN_LABELED_REAL_PHOTOS", "provided by the user; needs independent review"),
    "open": ("open-images-v7-validation", "HUMAN_LABELED_OPEN_DATA_OPEN_IMAGES_V7",
             "Open Images V7 human-drawn and human-verified boxes; each image has its own CC BY license"),
    "hard": ("open-images-v7-hard", "HUMAN_LABELED_OPEN_DATA_HARD_TIER",
             "Open Images V7 boxes, rules fixed in advance: look-alike negatives, truncated, small, dark objects"),
    "coco": ("coco-val2017", "HUMAN_LABELED_OPEN_DATA_COCO_VAL2017",
             "COCO val2017 human-drawn boxes and masks; a class counts as absent when COCO has no annotation of it"),
    "video": ("davis-2017-frames", "HUMAN_LABELED_OPEN_VIDEO_FRAMES",
              "DAVIS 2017 human-drawn masks on sampled video frames; box is the tight rectangle around the mask"),
}


def import_labeled(labels_json: Path, datasets: Path = DATASETS, force: bool = False, name: str = "real") -> int:
    if name not in KINDS:
        raise ValueError(f"dataset name must be one of {sorted(KINDS)}")
    source = json.loads(labels_json.read_text(encoding="utf-8"))
    items = source.get("cases")
    if not isinstance(items, list) or not items:
        raise ValueError("the labels file needs a non-empty 'cases' list")
    manifest_path = datasets / f"{name}_manifest.json"
    if manifest_path.exists() and not force:
        raise FileExistsError(f"{name}_manifest.json exists. Use --force to replace it on purpose.")
    seen: set[str] = set()
    prepared: list[tuple[dict[str, Any], Image.Image, Path, Path]] = []
    for item in items:
        case_id = item["id"]
        if not CASE_ID.match(case_id) or case_id in seen:
            raise ValueError(f"invalid or repeated case id: {case_id!r}")
        seen.add(case_id)
        photo = Path(item["image_source"]).expanduser().resolve()
        if not photo.is_file() or photo.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"{case_id}: image_source must be an existing png or jpg file")
        image, original = _normalized(photo)
        _check_label(item, original)
        prepared.append((item, image, photo, Path(f"{name}/{case_id}{photo.suffix.lower().replace('.jpeg', '.jpg')}")))
    for item in prepared:
        if item[0].get("recovery_case") and item[0]["recovery_case"] not in seen:
            raise ValueError(f"{item[0]['id']}: unknown recovery_case {item[0]['recovery_case']}")

    (datasets / name).mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    for item, image, photo, relative in prepared:
        target = datasets / relative
        if target.exists() and not force:
            raise FileExistsError(target)
        if target.suffix == ".png":
            image.save(target, "PNG")
        else:
            image.convert("RGB").save(target, "JPEG", quality=92)
        if target.stat().st_size > MAX_IMAGE_BYTES:
            target.unlink()
            raise ValueError(f"{item['id']}: stored image is over {MAX_IMAGE_BYTES:,} bytes; use a smaller photo")
        original = _normalized(photo)[1]
        truth = dict(item["ground_truth"])
        if truth.get("bbox"):
            truth["bbox"] = _scaled_box(truth["bbox"], original, image.size)
        cases.append({
            "id": item["id"], "title": item.get("title", item["id"]), "image": relative.as_posix(),
            "condition": item.get("condition", "other"), "concept": item.get("concept", "red safety tag"),
            "ground_truth": truth, "recovery_case": item.get("recovery_case"),
            "note": item.get("note", ""), "label_provenance": item["label_provenance"],
            "image_sha256": sha256_file(target), "source_sha256": sha256_file(photo),
            "stored_size": list(image.size), "original_size": list(original),
            **{key: item[key] for key in ("source_url", "license", "attribution") if key in item},
        })
    atomic_write_text(manifest_path, json.dumps({
        "dataset_id": KINDS[name][0], "type": KINDS[name][1], "annotation_status": KINDS[name][2],
        "imported_at": datetime.now(timezone.utc).isoformat(), "cases": cases}, indent=2))
    return len(cases)


def remove_import(datasets: Path = DATASETS) -> None:
    """Delete a previous private import (used by tests and by --force workflows)."""
    shutil.rmtree(datasets / "real", ignore_errors=True)
    (datasets / "real_manifest.json").unlink(missing_ok=True)


def adjudicate(case_id: str, reason: str, by: str, name: str = "open", datasets: Path = DATASETS) -> dict[str, Any]:
    """A named person marks a doubtful label as unknown, so it is no longer scored.

    Label errors can flip conclusions (Northcutt et al. 2021), but silently editing labels would hide
    that. The original label, the person and the reason stay in label_provenance, and the image hash
    is unchanged. Unknown cases are reported separately and never count as a model miss.
    """
    if name not in KINDS:
        raise ValueError(f"dataset name must be one of {sorted(KINDS)}")
    if not by.strip() or not reason.strip():
        raise ValueError("an adjudication needs a person (--by) and a reason")
    path = datasets / f"{name}_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for item in manifest["cases"]:
        if item["id"] == case_id:
            if item["ground_truth"]["visibility"] == "unknown":
                raise ValueError(f"{case_id} is already unknown")
            item["label_provenance"]["adjudication"] = {
                "original_label": item["ground_truth"], "by": by.strip(), "reason": reason.strip(),
                "at": datetime.now(timezone.utc).isoformat()}
            item["ground_truth"] = {"visibility": "unknown", "bbox": None}
            atomic_write_text(path, json.dumps(manifest, indent=2))
            return item
    raise ValueError(f"no case {case_id} in {path.name}")
