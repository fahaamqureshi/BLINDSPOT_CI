"""A real, stable evidence set from COCO val2017: human boxes and human masks, rules fixed in advance.

COCO annotators drew a polygon around every instance of 80 classes. We use three red or road-safety
objects: fire hydrant, stop sign, traffic light. The box is the tight rectangle of the human polygon, and
the polygon itself is kept so mask quality can be scored too. Nothing here comes from SAM or Muse.

Positive photos have exactly one non-crowd instance of the target. Conditions, in priority order:
  low_light        mean brightness inside the box below 70 of 255
  truncated        the box touches the photo edge
  lookalike_scene  another of the three classes is also in the photo
  small_object     box under 3 percent of the photo
  normal           none of the above
Negatives (the class has no annotation in the photo; COCO is thorough but not a verified-absence set):
  other_object     the target is not annotated but one of the other two classes is
  absent           none of the three classes is annotated, and the photo shows a street (car, bus or truck)

Photos with an EXIF rotation are skipped because the boxes could be misaligned. Each image must decode to the
size the annotation file states. Only images.cocodataset.org over http is allowed, with a size cap.

    python -I scripts/fetch_coco.py
    python -m blindspot_ci.cli import-photos DIR/coco-labels.json --dataset coco
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from remote_zip import open_zip

spec = importlib.util.spec_from_file_location("fetch_open_data", Path(__file__).with_name("fetch_open_data.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ZIP_URL = "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
HOST = "images.cocodataset.org"
TARGETS = {"fire hydrant": 11, "stop sign": 13, "traffic light": 10}
STREET = {3, 6, 8}  # car, bus, truck
QUOTA = {"normal": 24, "low_light": 10, "truncated": 14, "lookalike_scene": 10, "small_object": 24,
         "other_object": 20, "absent": 30}
LOW_LIGHT, SMALL = 70, 0.03
MAX_BYTES = 10 << 20


def download(url: str, path: Path, width: int, height: int) -> bool:
    if urlsplit(url).hostname != HOST:
        return False
    if not path.is_file():
        request = urllib.request.Request(url, headers=base.HEADERS)
        with urllib.request.urlopen(request, timeout=40) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return False
        path.write_bytes(data)
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.size == (width, height) and base.upright_ok(path)
    except (OSError, SyntaxError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "blindspot_coco"))
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    out = Path(args.out)
    (out / "photos").mkdir(parents=True, exist_ok=True)
    cache = out / "instances_val2017.json"
    if not cache.is_file():
        print("reading the COCO val annotations (about 6 MB over the wire) ...", flush=True)
        cache.write_bytes(open_zip(ZIP_URL).read("annotations/instances_val2017.json"))
    data = json.loads(cache.read_text(encoding="utf-8"))
    images = {i["id"]: i for i in data["images"]}
    licenses = {lic["id"]: lic["name"] for lic in data["licenses"]}
    by_image: dict[int, list[dict]] = defaultdict(list)
    for a in data["annotations"]:
        by_image[a["image_id"]].append(a)
    names = {v: k for k, v in TARGETS.items()}
    rng = random.Random(args.seed)
    ids = sorted(images)
    rng.shuffle(ids)
    counts: dict[str, int] = defaultdict(int)
    cases: list[dict] = []

    def provenance(image_id: int, extra: dict) -> dict:
        info = images[image_id]
        return {"annotator": "COCO annotators (crowd workers; box derived from their polygon)",
                "labeled_at": "COCO 2017 release", "dataset": "COCO val2017", "image_id": image_id,
                "license": licenses.get(info["license"], "unknown"), "flickr_url": info.get("flickr_url"),
                "landing_page": "https://cocodataset.org/#download", **extra}

    for image_id in ids:
        if all(counts[k] >= v for k, v in QUOTA.items()):
            break
        info, anns = images[image_id], by_image.get(image_id, [])
        present = {a["category_id"] for a in anns}
        targets_here = present & set(names)
        path = out / "photos" / f"{image_id:012d}.jpg"
        width, height = info["width"], info["height"]
        own_by_class = {c: [a for a in anns if a["category_id"] == c] for c in targets_here}
        single = [(c, v[0]) for c, v in own_by_class.items() if len(v) == 1 and not v[0]["iscrowd"]]
        if single:
            category, ann = rng.choice(single)
            x, y, w, h = ann["bbox"]
            box = [max(0, int(x)), max(0, int(y)), min(width, int(x + w) + 1), min(height, int(y + h) + 1)]
            if box[2] - box[0] < 4 or box[3] - box[1] < 4 or not download(info["coco_url"], path, width, height):
                continue
            with Image.open(path) as image:
                gray = image.convert("L").crop(tuple(box))
                gray.thumbnail((128, 128))
                inside = sum(gray.getdata()) / max(1, gray.width * gray.height)
            edge = box[0] <= 1 or box[1] <= 1 or box[2] >= width - 1 or box[3] >= height - 1
            others = sorted(names[c] for c in targets_here if c != category)
            area = (box[2] - box[0]) * (box[3] - box[1]) / (width * height)
            condition = ("low_light" if inside < LOW_LIGHT else "truncated" if edge else "lookalike_scene" if others
                         else "small_object" if area < SMALL else "normal")
            if counts[condition] >= QUOTA[condition]:
                continue
            counts[condition] += 1
            concept = names[category]
            cases.append({"id": f"cc_{condition}_{counts[condition]:02d}",
                          "title": f"{concept} ({condition.replace('_', ' ')})",
                          "image_source": str(path), "condition": condition, "concept": concept,
                          "ground_truth": {"visibility": "visible", "bbox": box},
                          "label_provenance": provenance(image_id, {"human_polygons": ann["segmentation"],
                                                                   "coco_annotation_id": ann["id"],
                                                                   "others_present": others})})
            continue
        # negative: ask for a class that has no annotation in this photo
        wanted = rng.choice(sorted(TARGETS))
        if TARGETS[wanted] in present:
            continue
        others_present = sorted(names[c] for c in targets_here)
        kind = "other_object" if others_present else "absent"
        if counts[kind] >= QUOTA[kind] or (kind == "absent" and not present & STREET):
            continue
        if not download(info["coco_url"], path, width, height):
            continue
        counts[kind] += 1
        cases.append({"id": f"cc_{kind}_{counts[kind]:02d}", "title": f"no {wanted} ({kind.replace('_', ' ')})",
                      "image_source": str(path), "condition": kind, "concept": wanted,
                      "ground_truth": {"visibility": "absent", "bbox": None},
                      "label_provenance": provenance(image_id, {"others_present": others_present,
                                                               "note": "the class has no COCO annotation in this photo"})})
    (out / "coco-labels.json").write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")
    print(f"wrote {len(cases)} cases: {dict(counts)}\nnext: python -m blindspot_ci.cli import-photos "
          f"{out / 'coco-labels.json'} --dataset coco")
    return 0 if cases else 1


if __name__ == "__main__":
    sys.exit(main())
