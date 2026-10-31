"""Build a labeled evidence set from Open Images V7 (validation and test splits): real photos, human boxes.

Task: red safety objects (fire hydrant, stop sign). Boxes come from Open Images annotators, never
from SAM or Muse. Negatives are images where annotators verified the class is absent. Each image keeps
its own CC BY license, author and landing page in label_provenance.

Conditions are measured, not guessed:
  low_light    mean luminance below 70 of 255
  occlusion    annotator flag IsOccluded
  truncated    annotator flag IsTruncated (object cut by the image edge)
  small_object box under 3 percent of the image
  normal       none of the above
  absent       annotator-verified negative

Usage (run with -I because the downloaded CSVs are untrusted data):
    python -I scripts/fetch_open_data.py [--out DIR] [--seed 7]
    python -m blindspot_ci.cli import-photos DIR/open-labels.json --dataset open
Downloads about 40 MB of CSV files once, then roughly 30 photos. Nothing here is sent to Meta.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import random
import re
import sys
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image

BASE = "https://storage.googleapis.com/openimages"
SPLITS = ("validation", "test")


def split_files(split: str) -> dict[str, str]:
    return {f"{split}-boxes": f"{BASE}/v5/{split}-annotations-bbox.csv",
            f"{split}-images": f"{BASE}/2018_04/{split}/{split}-images-with-rotation.csv",
            f"{split}-labels": f"{BASE}/v5/{split}-annotations-human-imagelabels-boxable.csv"}
TARGETS = ["Fire hydrant", "Stop sign"]
QUOTA = {"normal": 6, "occlusion": 6, "truncated": 4, "small_object": 4, "low_light": 4, "absent": 6}
LOW_LIGHT_LUMA = 70
SMALL_FRACTION = 0.03
HEADERS = {"User-Agent": "blindspot-ci-fetch/1.0 (research; open data)"}


def fetch(url: str, target: Path) -> None:
    if target.is_file() and target.stat().st_size > 0:
        return
    print(f"downloading {url.rsplit('/', 1)[-1]} ...", flush=True)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=120) as response, open(target, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


MAX_PHOTO_BYTES = 25 << 20


def download_photo(url: str, image_id: str, expected_md5: str, path: Path, timeout: int = 40) -> bool:
    """Fetch one photo safely: https only (also after redirects), a size cap, a strict file name, and the
    Open Images MD5. The CSV is data from outside, so none of its fields is trusted."""
    if not re.fullmatch(r"[A-Za-z0-9]+", image_id) or not url.startswith("https://"):
        return False
    if path.is_file():
        return md5_matches(path.read_bytes(), expected_md5)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if not response.geturl().startswith("https://"):
            return False
        data = response.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES or not md5_matches(data, expected_md5):
        return False
    path.write_bytes(data)
    return True


def md5_matches(data: bytes, expected: str) -> bool:
    digest = hashlib.md5(data).digest()
    return expected in (base64.b64encode(digest).decode(), digest.hex())


def luminance(path: Path) -> float:
    with Image.open(path) as image:
        gray = image.convert("L")
        gray.thumbnail((128, 128))
        pixels = list(gray.getdata())
    return sum(pixels) / len(pixels)


def upright_ok(path: Path) -> bool:
    """Skip images with an EXIF orientation: Open Images boxes assume the stored pixel layout."""
    with Image.open(path) as image:
        return image.getexif().get(274, 1) in (0, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "blindspot_openimages"))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    out = Path(args.out)
    (out / "photos").mkdir(parents=True, exist_ok=True)
    fetch(f"{BASE}/v5/class-descriptions-boxable.csv", out / "classes.csv")
    for split in SPLITS:
        for key, url in split_files(split).items():
            fetch(url, out / f"{key}.csv")

    with open(out / "classes.csv", encoding="utf-8", newline="") as handle:
        names = {row[1]: row[0] for row in csv.reader(handle)}
    mids = {names[t]: t for t in TARGETS}  # MID -> class name
    boxes: dict[str, list[dict]] = defaultdict(list)
    for split in SPLITS:
        for r in read_csv(out / f"{split}-boxes.csv"):
            if r["LabelName"] in mids:
                boxes[r["ImageID"]].append(r)
    verified: dict[str, set[str]] = defaultdict(set)  # image -> classes annotators verified absent
    for split in SPLITS:
        for r in read_csv(out / f"{split}-labels.csv"):
            if r["LabelName"] in mids and r["Confidence"] == "0":
                verified[r["ImageID"]].add(mids[r["LabelName"]].lower())
    negatives = list(verified)
    meta = {}
    for split in SPLITS:
        meta.update({r["ImageID"]: r for r in read_csv(out / f"{split}-images.csv")})

    visible = []  # one clear, non-group, non-depiction box of one target class
    for image_id, items in boxes.items():
        m = meta.get(image_id)
        if not m or m.get("Rotation") not in ("", "0", "0.0", None) or len(items) != 1:
            continue
        b = items[0]
        if b["IsGroupOf"] == "1" or b["IsDepiction"] == "1":
            continue
        visible.append((image_id, b))
    rng = random.Random(args.seed)
    rng.shuffle(visible)
    rng.shuffle(negatives)
    print(f"{len(visible)} candidate visible images, {len(negatives)} verified negatives")

    def get_image(image_id: str) -> Path | None:
        m = meta[image_id]
        path = out / "photos" / f"{image_id}.jpg"
        try:
            if not download_photo(m["OriginalURL"], image_id, m["OriginalMD5"], path):
                return None
            return path if upright_ok(path) else None
        except (OSError, ValueError) as exc:  # a dead Flickr link is normal; try the next image
            print(f"  skip {image_id}: {type(exc).__name__}")
            return None

    counts = defaultdict(int)
    cases: list[dict] = []

    def provenance(image_id: str) -> dict:
        m = meta[image_id]
        return {"annotator": "Open Images V7 human annotators", "labeled_at": "Open Images V7 release",
                "dataset": "Open Images V7 (validation and test splits)", "image_id": image_id, "license": m["License"],
                "author": m["Author"], "landing_page": m["OriginalLandingURL"], "source_md5": m["OriginalMD5"]}

    for image_id, b in visible:
        if all(counts[k] >= QUOTA[k] for k in QUOTA if k != "absent"):
            break
        path = get_image(image_id)
        if path is None:
            continue
        with Image.open(path) as image:
            width, height = image.size
        x1, x2 = float(b["XMin"]) * width, float(b["XMax"]) * width
        y1, y2 = float(b["YMin"]) * height, float(b["YMax"]) * height
        box = [max(0, int(x1)), max(0, int(y1)), min(width, int(x2) + 1), min(height, int(y2) + 1)]
        area = (box[2] - box[0]) * (box[3] - box[1]) / (width * height)
        if luminance(path) < LOW_LIGHT_LUMA:
            condition = "low_light"
        elif b["IsOccluded"] == "1":
            condition = "occlusion"
        elif b["IsTruncated"] == "1":
            condition = "truncated"
        elif area < SMALL_FRACTION:
            condition = "small_object"
        else:
            condition = "normal"
        if counts[condition] >= QUOTA[condition]:
            continue
        counts[condition] += 1
        concept = mids[b["LabelName"]].lower()
        cases.append({"id": f"oi_{condition}_{counts[condition]:02d}", "title": f"{concept} ({condition.replace('_', ' ')})",
                      "image_source": str(path), "condition": condition, "concept": concept,
                      "ground_truth": {"visibility": "visible", "bbox": box}, "label_provenance": provenance(image_id)})
        print(f"  {cases[-1]['id']}: {concept}, box {box}")

    for image_id in negatives:
        if counts["absent"] >= QUOTA["absent"]:
            break
        if image_id in boxes or image_id not in meta or meta[image_id].get("Rotation") not in ("", "0", "0.0", None):
            continue
        path = get_image(image_id)
        if path is None:
            continue
        counts["absent"] += 1
        concept = min(verified[image_id])
        cases.append({"id": f"oi_absent_{counts['absent']:02d}", "title": f"no {concept} (verified absent)",
                      "image_source": str(path), "condition": "absent", "concept": concept,
                      "ground_truth": {"visibility": "absent", "bbox": None},
                      "label_provenance": {**provenance(image_id), "note": "annotators verified this class is absent"}})
    (out / "open-labels.json").write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")
    print(f"\nwrote {len(cases)} cases: {dict(counts)}\nnext: python -m blindspot_ci.cli import-photos "
          f"{out / 'open-labels.json'} --dataset open")
    return 0 if cases else 1


if __name__ == "__main__":
    sys.exit(main())
