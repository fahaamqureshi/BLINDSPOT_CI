"""Mask-quality scoring: how well does the model's mask cover a mask a person drew?

Box overlap hides bad outlines. DAVIS annotators drew a pixel mask on every frame, so for the video set
we can score the mask itself (Jaccard index, the J measure of Perazzi et al. 2016). Saved SAM masks are
stored as outline paths (M and L commands, several sub-paths, holes drawn inside others). Python draws
them back into pixels. No model is called here.
"""
from __future__ import annotations

import re
from typing import Any

from PIL import Image, ImageChops, ImageDraw

TOKEN = re.compile(r"([MLZ])|(-?\d+(?:\.\d+)?)")


def _subpaths(svg_path: str) -> list[list[tuple[float, float]]]:
    paths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    numbers: list[float] = []
    command = ""
    for letter, number in TOKEN.findall(svg_path):
        if letter:
            if letter == "M" and current:
                paths.append(current)
                current = []
            command = letter
            continue
        numbers.append(float(number))
        if len(numbers) == 2 and command in {"M", "L"}:
            current.append((numbers[0], numbers[1]))
            numbers = []
    if current:
        paths.append(current)
    return [p for p in paths if len(p) >= 3]


def rasterize(mask: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    """Saved mask dict (bounds_xyxy, width, height, svg_path) to a full-size 1-bit image."""
    left, top, right, bottom = mask["bounds_xyxy"]
    sx = (right - left) / mask["width"]
    sy = (bottom - top) / mask["height"]
    result = Image.new("1", size, 0)
    for points in _subpaths(mask["svg_path"]):
        layer = Image.new("1", size, 0)
        ImageDraw.Draw(layer).polygon([(left + x * sx, top + y * sy) for x, y in points], fill=1)
        result = ImageChops.logical_xor(result, layer)  # even-odd: an inner outline is a hole
    return result


def _count(image: Image.Image) -> int:
    return image.histogram()[255] if image.mode == "L" else sum(1 for v in image.getdata() if v)


def mask_iou(a: Image.Image, b: Image.Image) -> float:
    inter = _count(ImageChops.logical_and(a, b).convert("L"))
    union = _count(ImageChops.logical_or(a, b).convert("L"))
    return inter / union if union else 1.0


def human_mask_from_labels(labels: Image.Image) -> Image.Image:
    """Any labelled pixel (non-zero) is the object."""
    return labels.convert("L").point(lambda v: 255 if v else 0).convert("1")
