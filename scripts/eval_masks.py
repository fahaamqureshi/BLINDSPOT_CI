"""Score SAM masks of a saved video run against the masks DAVIS annotators drew. No model call, free.

    python -I scripts/eval_masks.py --run 8f6003378706480a

For each frame the detection whose box best matches the human box is compared with the human mask
(Jaccard index J). Human masks are read from the DAVIS zip with range requests and kept in the temp folder.
Reports the mean, the share of frames at J of 0.5 and 0.75 or better, and the worst frames. Writes
artifacts/mask-eval-<run>.json next to the run files.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from remote_zip import open_zip

from blindspot_ci.experiment.mask_eval import human_mask_from_labels, mask_iou, rasterize
from blindspot_ci.experiment.scoring import box_iou

URL = "https://data.vision.ee.ethz.ch/csergi/share/davis/DAVIS-2017-trainval-480p.zip"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--runs-dir", default="artifacts/runs")
    args = parser.parse_args()
    run = json.loads((Path(args.runs_dir) / f"{args.run}.json").read_text(encoding="utf-8"))
    cache = Path(tempfile.gettempdir()) / "blindspot_davis" / "human_masks"
    cache.mkdir(parents=True, exist_ok=True)
    archive = None
    rows = []
    for step in run["steps"]:
        prov = (step["ground_truth"] or {}).get("label_provenance") or {}
        if "clip" not in prov or not step["ground_truth"]["bbox"]:
            continue
        clip, frame = prov["clip"], prov["frame"]
        size = (step["case"]["width"], step["case"]["height"])
        path = cache / f"{clip}_{frame:05d}.png"
        if not path.is_file():
            archive = archive or open_zip(URL)
            path.write_bytes(archive.read(f"DAVIS/Annotations/480p/{clip}/{frame:05d}.png"))
        with Image.open(path) as labels:
            human = human_mask_from_labels(labels)
        detections = [d for d in (step["prediction"] or {}).get("detections", []) if d.get("mask") and d.get("bbox")]
        if not detections:
            rows.append({"case": step["case"]["id"], "clip": clip, "condition": step["case"]["condition"], "j": 0.0,
                         "note": "no mask returned"})
            continue
        best = max(detections, key=lambda d: box_iou(tuple(d["bbox"]), tuple(step["ground_truth"]["bbox"])))
        j = mask_iou(rasterize(best["mask"], size), human)
        rows.append({"case": step["case"]["id"], "clip": clip, "condition": step["case"]["condition"], "j": round(j, 4)})
    values = [r["j"] for r in rows]
    by_condition: dict[str, list[float]] = {}
    by_clip: dict[str, list[float]] = {}
    for r in rows:
        by_condition.setdefault(r["condition"], []).append(r["j"])
        by_clip.setdefault(r["clip"], []).append(r["j"])
    summary = {
        "run": args.run, "frames": len(rows), "mean_j": round(statistics.mean(values), 4),
        "median_j": round(statistics.median(values), 4),
        "share_j_at_least_0_5": round(sum(v >= 0.5 for v in values) / len(values), 4),
        "share_j_at_least_0_75": round(sum(v >= 0.75 for v in values) / len(values), 4),
        "by_condition": {k: round(statistics.mean(v), 4) for k, v in by_condition.items()},
        "by_clip": {k: round(statistics.mean(v), 4) for k, v in sorted(by_clip.items(), key=lambda kv: statistics.mean(kv[1]))},
        "worst_frames": sorted(rows, key=lambda r: r["j"])[:8],
        "note": "J is mask overlap with a mask a person drew. Mean J weights every frame equally; frames of one clip are correlated.",
    }
    out = Path(args.runs_dir).parent / f"mask-eval-{args.run}.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "worst_frames"}, indent=2))
    print("worst:", [(r["case"], r["j"]) for r in summary["worst_frames"]])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
