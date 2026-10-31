"""Measured corruptions of labeled photos, in the style of ImageNet-C and COCO-C.

Hendrycks and Dietterich (ICLR 2019) and Michaelis et al. (2019) standardize corruption types at five
severities. These functions follow that idea with Pillow only. They never move or resize pixels, so a
human box stays exact on every variant, unlike a generative edit. Output is deterministic for a seed.
"""
from __future__ import annotations

import io
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

from blindspot_ci.experiment.cases import CASE_ID, DATASETS, Dataset, image_path, sha256_file
from blindspot_ci.media import MAX_IMAGE_BYTES

SEVERITIES = (1, 2, 3, 4, 5)
MAX_VARIANTS = 60
CODE = "blindspot_ci.experiment.corruptions"


NOISE_MAX_PIXELS = 1_000_000


def low_light(image: Image.Image, severity: int, rng: random.Random) -> Image.Image:
    return ImageEnhance.Brightness(image).enhance((0.6, 0.45, 0.3, 0.2, 0.12)[severity - 1])


def noise(image: Image.Image, severity: int, rng: random.Random) -> Image.Image:
    sigma = (8, 16, 28, 40, 56)[severity - 1]
    width, height = image.size
    scale = min(1.0, (NOISE_MAX_PIXELS / (width * height)) ** 0.5)  # bound the Python loop
    gw, gh = max(1, int(width * scale)), max(1, int(height * scale))
    data = bytes(min(255, max(0, int(rng.gauss(128, sigma)))) for _ in range(gw * gh))
    layer = Image.frombytes("L", (gw, gh), data)
    if (gw, gh) != (width, height):
        layer = layer.resize((width, height), Image.BILINEAR)
    layer = layer.convert("RGB")
    return ImageChops.add(image, layer, scale=1.0, offset=-128)


def blur(image: Image.Image, severity: int, rng: random.Random) -> Image.Image:
    radius = (0.4, 0.8, 1.4, 2.2, 3.2)[severity - 1] * max(image.size) / 400
    return image.filter(ImageFilter.GaussianBlur(radius))


def jpeg(image: Image.Image, severity: int, rng: random.Random) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=(40, 25, 15, 8, 4)[severity - 1])
    return Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")


def fog(image: Image.Image, severity: int, rng: random.Random) -> Image.Image:
    haze = Image.new("RGB", image.size, (215, 218, 222))
    return Image.blend(image, haze, (0.2, 0.35, 0.5, 0.65, 0.8)[severity - 1])


def contrast(image: Image.Image, severity: int, rng: random.Random) -> Image.Image:
    return ImageEnhance.Contrast(image).enhance((0.6, 0.4, 0.25, 0.15, 0.08)[severity - 1])


CORRUPTIONS: dict[str, Callable[[Image.Image, int, random.Random], Image.Image]] = {
    "low_light": low_light, "noise": noise, "blur": blur, "jpeg": jpeg, "fog": fog,
    "contrast": contrast}


def _save(image: Image.Image, target: Path) -> None:
    for quality in (95, 85, 70):
        image.save(target, "JPEG", quality=quality)
        if target.stat().st_size <= MAX_IMAGE_BYTES:
            return
    raise ValueError(f"{target.name} stays over {MAX_IMAGE_BYTES:,} bytes")


def generate_corruptions(source: Dataset, corruptions: list[str], severities: list[int],
                         case_ids: list[str] | None = None, seed: int = 7,
                         datasets: Path = DATASETS) -> list[dict[str, Any]]:
    """One variant per (case, corruption, severity). Boxes and absent labels carry over unchanged."""
    unknown = [c for c in corruptions if c not in CORRUPTIONS]
    if unknown or not corruptions:
        raise ValueError(f"unknown corruption {unknown}; choose from {sorted(CORRUPTIONS)}")
    if not severities or any(s not in SEVERITIES for s in severities):
        raise ValueError("severity must be 1 to 5")
    chosen = [c for c in source.cases.values()
              if c.visibility != "unknown" and (case_ids is None or c.id in case_ids)]
    jobs = [(c, name, sev) for c in chosen for name in corruptions for sev in severities]
    if not jobs:
        raise ValueError("no scoreable source cases selected")
    if len(jobs) > MAX_VARIANTS:
        raise ValueError(f"{len(jobs)} variants requested; the limit is {MAX_VARIANTS} per call")
    out_dir = datasets / "corrupted"
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for case, name, severity in jobs:
        case_id = f"{case.id}_{name}_s{severity}"
        if not CASE_ID.match(case_id):
            raise ValueError(f"derived case id {case_id!r} is too long or unsafe")
        rng = random.Random(f"{seed}:{case_id}")
        with Image.open(image_path(case, datasets)) as original:
            result = CORRUPTIONS[name](original.convert("RGB"), severity, rng)
        target = out_dir / f"{case_id}.jpg"
        _save(result, target)
        truth = {"visibility": case.visibility,
                 "bbox": list(case.ground_truth_box) if case.ground_truth_box else None}
        entries.append({
            "id": case_id, "title": f"{case.title} ({name.replace('_', ' ')}, severity {severity})",
            "image": f"corrupted/{case_id}.jpg", "condition": f"{name}_s{severity}", "concept": case.concept,
            "ground_truth": truth,
            "note": "Measured corruption of a labeled photo. Pixels were not moved, so the label is exact.",
            "label_provenance": {**case.label_provenance, "derived_from": case.id, "corruption": name,
                                 "severity": severity, "seed": seed, "code": CODE},
            "image_sha256": sha256_file(target)})
    return entries
