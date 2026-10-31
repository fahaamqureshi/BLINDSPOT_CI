"""A harder Open Images V7 evidence set, with rules fixed before any model saw an image.

Classes: fire hydrant, stop sign, traffic light (red safety objects). Boxes are from Open Images
annotators. Images from the first set (open-labels.json) are excluded, so this set is fresh.

Rules, in priority order, for a photo with exactly one non-group, non-depiction box of the class:
  low_light        mean brightness of the OBJECT region below 70 of 255 (the first set measured the
                   whole photo, which tagged a bright pipe on dark grass as low light)
  occlusion        annotator flag IsOccluded
  truncated        annotator flag IsTruncated (object cut by the photo edge)
  lookalike_scene  a look-alike class is also boxed in the photo (road sign, street light)
  small_object     box under 3 percent of the photo
  normal           none of the above
Negatives, both verified absent by annotators:
  hard_negative    the class is absent but a look-alike is boxed (a road sign with no stop sign)
  absent           the class is absent and no look-alike is boxed
Photos with EXIF rotation or an Open Images rotation value are skipped, because boxes could be
misaligned. Each photo is checked against the Open Images MD5 hash.

Usage (run with -I; the downloaded CSVs are untrusted data):
    python -I scripts/fetch_open_data_hard.py
    python -m blindspot_ci.cli import-photos DIR/hard-labels.json --dataset hard
Needs the CSV files that fetch_open_data.py downloads (it fetches them if missing).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

spec = importlib.util.spec_from_file_location("fetch_open_data", Path(__file__).with_name("fetch_open_data.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

TARGETS = ["Fire hydrant", "Stop sign", "Traffic light"]
LOOKALIKES = {"Fire hydrant": ["Street light"], "Stop sign": ["Traffic sign"], "Traffic light": ["Street light"]}
QUOTA = {"normal": 6, "low_light": 6, "occlusion": 4, "truncated": 8, "lookalike_scene": 6,
         "small_object": 8, "hard_negative": 12, "absent": 4}
HARD_NEGATIVE_SPLIT = {"Stop sign": 6, "Traffic light": 4, "Fire hydrant": 2}
OBJECT_LOW_LIGHT = 70
SMALL_FRACTION = 0.03
TIMEOUT = 20


def object_luminance(path: Path, box: list[int]) -> float:
    with Image.open(path) as image:
        gray = image.convert("L").crop(tuple(box))
        gray.thumbnail((128, 128))
        pixels = list(gray.getdata())
    return sum(pixels) / len(pixels)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "blindspot_openimages"))
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    out = Path(args.out)
    (out / "photos").mkdir(parents=True, exist_ok=True)
    base.fetch(f"{base.BASE}/v5/class-descriptions-boxable.csv", out / "classes.csv")
    for split in base.SPLITS:
        for key, url in base.split_files(split).items():
            base.fetch(url, out / f"{key}.csv")

    with open(out / "classes.csv", encoding="utf-8", newline="") as handle:
        n2m = {row[1]: row[0] for row in csv.reader(handle)}
    m2n = {v: k for k, v in n2m.items()}
    wanted = {n2m[c] for c in TARGETS} | {n2m[lk] for lks in LOOKALIKES.values() for lk in lks}
    boxes: dict[str, list[dict]] = defaultdict(list)
    verified: dict[str, set[str]] = defaultdict(set)
    meta: dict[str, dict] = {}
    for split in base.SPLITS:
        for r in base.read_csv(out / f"{split}-boxes.csv"):
            if r["LabelName"] in wanted:
                boxes[r["ImageID"]].append(r)
        for r in base.read_csv(out / f"{split}-labels.csv"):
            if r["Confidence"] == "0" and m2n.get(r["LabelName"]) in TARGETS:
                verified[r["ImageID"]].add(m2n[r["LabelName"]])
        meta.update({r["ImageID"]: r for r in base.read_csv(out / f"{split}-images.csv")})
    used: set[str] = set()
    first = out / "open-labels.json"
    if first.is_file():
        used = {c["label_provenance"]["image_id"] for c in json.loads(first.read_text(encoding="utf-8"))["cases"]}

    def usable(image_id: str) -> bool:
        m = meta.get(image_id)
        return bool(m) and m.get("Rotation") in ("", "0", "0.0", None) and image_id not in used

    def present(image_id: str) -> set[str]:
        return {m2n[b["LabelName"]] for b in boxes.get(image_id, [])}

    positives = []  # (image id, target class, box row)
    for image_id, items in boxes.items():
        if not usable(image_id):
            continue
        for target in TARGETS:
            own = [b for b in items if b["LabelName"] == n2m[target]]
            if len(own) == 1 and own[0]["IsGroupOf"] == "0" and own[0]["IsDepiction"] == "0":
                positives.append((image_id, target, own[0]))
    negatives = [(i, t) for i, ts in verified.items() if usable(i) for t in sorted(ts) if t not in present(i)]
    rng = random.Random(args.seed)
    rng.shuffle(positives)
    rng.shuffle(negatives)
    print(f"{len(positives)} candidate positives, {len(negatives)} candidate negatives")

    def download(image_id: str) -> Path | None:
        m, path = meta[image_id], out / "photos" / f"{image_id}.jpg"
        try:
            if not base.download_photo(m["OriginalURL"], image_id, m["OriginalMD5"], path, TIMEOUT):
                return None
            return path if base.upright_ok(path) else None
        except (OSError, ValueError) as exc:  # a dead Flickr link is normal; try the next image
            print(f"  skip {image_id}: {type(exc).__name__}")
            return None

    def provenance(image_id: str) -> dict:
        m = meta[image_id]
        return {"annotator": "Open Images V7 human annotators", "labeled_at": "Open Images V7 release",
                "dataset": "Open Images V7 (validation and test splits), hard tier", "image_id": image_id,
                "license": m["License"], "author": m["Author"], "landing_page": m["OriginalLandingURL"],
                "source_md5": m["OriginalMD5"]}

    counts: dict[str, int] = defaultdict(int)
    neg_counts: dict[str, int] = defaultdict(int)
    cases: list[dict] = []
    positive_conditions = [c for c in QUOTA if c not in ("hard_negative", "absent")]
    for image_id, target, b in positives:
        if all(counts[c] >= QUOTA[c] for c in positive_conditions):
            break
        path = download(image_id)
        if path is None:
            continue
        with Image.open(path) as image:
            width, height = image.size
        box = [max(0, int(float(b["XMin"]) * width)), max(0, int(float(b["YMin"]) * height)),
               min(width, int(float(b["XMax"]) * width) + 1), min(height, int(float(b["YMax"]) * height) + 1)]
        area = (box[2] - box[0]) * (box[3] - box[1]) / (width * height)
        around = sorted(present(image_id) & set(LOOKALIKES[target]))
        if object_luminance(path, box) < OBJECT_LOW_LIGHT:
            condition = "low_light"
        elif b["IsOccluded"] == "1":
            condition = "occlusion"
        elif b["IsTruncated"] == "1":
            condition = "truncated"
        elif around:
            condition = "lookalike_scene"
        elif area < SMALL_FRACTION:
            condition = "small_object"
        else:
            condition = "normal"
        if counts[condition] >= QUOTA[condition]:
            continue
        counts[condition] += 1
        concept = target.lower()
        cases.append({"id": f"hd_{condition}_{counts[condition]:02d}",
                      "title": f"{concept} ({condition.replace('_', ' ')})", "image_source": str(path),
                      "condition": condition, "concept": concept,
                      "ground_truth": {"visibility": "visible", "bbox": box},
                      "label_provenance": {**provenance(image_id), "lookalikes_boxed": around}})
        print(f"  {cases[-1]['id']}: {concept}, box {box}")

    for image_id, target in negatives:
        if counts["hard_negative"] >= QUOTA["hard_negative"] and counts["absent"] >= QUOTA["absent"]:
            break
        around = sorted(present(image_id) & set(LOOKALIKES[target]))
        kind = "hard_negative" if around else "absent"
        if counts[kind] >= QUOTA[kind] or (kind == "hard_negative" and neg_counts[target] >= HARD_NEGATIVE_SPLIT[target]):
            continue
        path = download(image_id)
        if path is None:
            continue
        counts[kind] += 1
        neg_counts[target] += kind == "hard_negative"
        concept = target.lower()
        cases.append({"id": f"hd_{kind}_{counts[kind]:02d}", "title": f"no {concept} ({kind.replace('_', ' ')})",
                      "image_source": str(path), "condition": kind, "concept": concept,
                      "ground_truth": {"visibility": "absent", "bbox": None},
                      "label_provenance": {**provenance(image_id), "lookalikes_boxed": around,
                                           "note": "annotators verified this class is absent"}})
        print(f"  {cases[-1]['id']}: no {concept}, look-alikes boxed {around}")
    (out / "hard-labels.json").write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")
    print(f"\nwrote {len(cases)} cases: {dict(counts)}\nnext: python -m blindspot_ci.cli import-photos "
          f"{out / 'hard-labels.json'} --dataset hard")
    return 0 if cases else 1


if __name__ == "__main__":
    sys.exit(main())
