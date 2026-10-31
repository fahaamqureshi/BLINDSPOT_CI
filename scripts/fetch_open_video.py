"""Real video evidence: frames from DAVIS 2017 clips, with boxes taken from human-drawn masks.

DAVIS (Pont-Tuset et al. 2017) annotators drew a pixel mask of the object on every frame. A box is
the tight rectangle around that mask, so no model (SAM, Muse) ever supplies a label. A frame whose
mask is empty means the object is out of view, so it becomes an absent case. The text concept
(for example "bear") is the only part written by us; it comes from the clip name.

Only the chosen frames are read from the 833 MB zip, using HTTP range requests. DAVIS data is for
research use (see https://davischallenge.org/); the frames stay out of git and out of the ZIP.

Conditions are measured: low_light (object mean brightness under 70 of 255), truncated (box touches
the frame edge), small_object (box under 3 percent of the frame), absent (empty mask), else normal.

    python -I scripts/fetch_open_video.py
    python -m blindspot_ci.cli import-photos DIR/video-labels.json --dataset video
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from remote_zip import open_zip

URL = "https://data.vision.ee.ethz.ch/csergi/share/davis/DAVIS-2017-trainval-480p.zip"
CLIPS = {"bear": "bear", "blackswan": "black swan", "boat": "boat", "bus": "bus", "camel": "camel",
         "car-turn": "car", "dog": "dog", "elephant": "elephant", "flamingo": "flamingo", "goat": "goat",
         "koala": "koala", "mallard-fly": "duck", "rhino": "rhino", "soccerball": "soccer ball"}
FRAMES_PER_CLIP = 8
LOW_LIGHT, SMALL = 70, 0.03


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "blindspot_davis"))
    args = parser.parse_args()
    out = Path(args.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    z = open_zip(URL)
    names = set(z.namelist())
    cases: list[dict] = []
    for clip, concept in CLIPS.items():
        masks = sorted(n for n in names if n.startswith(f"DAVIS/Annotations/480p/{clip}/") and n.endswith(".png"))
        picks = sorted({round(i * (len(masks) - 1) / (FRAMES_PER_CLIP - 1)) for i in range(FRAMES_PER_CLIP)})
        for index in picks:
            mask = np.array(Image.open(io.BytesIO(z.read(masks[index]))))
            jpg = f"DAVIS/JPEGImages/480p/{clip}/{index:05d}.jpg"
            if jpg not in names:
                continue
            path = out / "frames" / f"{clip}_{index:05d}.jpg"
            path.write_bytes(z.read(jpg))
            with Image.open(path) as image:
                width, height = image.size
                gray = np.array(image.convert("L"))
            ys, xs = np.nonzero(mask)
            if len(xs) == 0:
                condition, truth = "absent", {"visibility": "absent", "bbox": None}
            else:
                box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
                inside = gray[mask > 0].mean()
                area = (box[2] - box[0]) * (box[3] - box[1]) / (width * height)
                edge = box[0] <= 0 or box[1] <= 0 or box[2] >= width or box[3] >= height
                condition = ("low_light" if inside < LOW_LIGHT else "truncated" if edge
                             else "small_object" if area < SMALL else "normal")
                truth = {"visibility": "visible", "bbox": box}
            cases.append({
                "id": f"dv_{clip.replace('-', '_')}_f{index:03d}", "title": f"{concept} in {clip}, frame {index}",
                "image_source": str(path), "condition": condition, "concept": concept, "ground_truth": truth,
                "label_provenance": {
                    "annotator": "DAVIS 2017 human annotators (pixel masks; box derived from mask)",
                    "labeled_at": "DAVIS 2017 release", "dataset": "DAVIS 2017 trainval 480p",
                    "clip": clip, "frame": index, "frames_in_clip": len(masks),
                    "license": "DAVIS terms, research use", "author": "Pont-Tuset et al.",
                    "landing_page": "https://davischallenge.org/davis2017/code.html"}})
        print(f"{clip}: {sum(1 for c in cases if c['label_provenance']['clip'] == clip)} frames")
    (out / "video-labels.json").write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")
    kinds: dict[str, int] = {}
    for c in cases:
        kinds[c["condition"]] = kinds.get(c["condition"], 0) + 1
    print(f"wrote {len(cases)} frames: {kinds}\nnext: python -m blindspot_ci.cli import-photos "
          f"{out / 'video-labels.json'} --dataset video")
    return 0


if __name__ == "__main__":
    sys.exit(main())
