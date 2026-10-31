# Live result on COCO val2017

Run `a165cd6773cd433a`, 2026-11-01. SAM 3.1 through the Meta Model API, 132 cases in a fixed order (mock
planner, so the order is scripted and not agent-chosen). Cost about $0.33. Source label `LIVE_META` on every step.

## Labels

COCO annotators drew a polygon around every instance of fire hydrant, stop sign and traffic light. The human box
is the tight rectangle of that polygon. Each positive photo has exactly one non-crowd instance. A negative photo
is one where COCO has no annotation of the requested class. Nothing was labeled by SAM or Muse. The fetcher is
`scripts/fetch_coco.py` (seed 17) and the polygons are kept for mask scoring.

## Result

119 of 132 passed at IoU 0.35.

| Condition | Passed | Cases |
| --- | --- | --- |
| normal | 24 | 24 |
| truncated | 14 | 14 |
| absent (street scene, class not annotated) | 29 | 30 |
| other object present | 19 | 20 |
| lookalike scene | 8 | 10 |
| small object (under 3 percent of the photo) | 19 | 24 |
| low light (mean brightness under 70) | 6 | 10 |

## What it shows

- Low light is the weakest slice: 4 of 10 failed, three of them with nothing returned.
- Small objects failed 5 of 24, mostly traffic lights and stop signs that were missed.
- Normal and truncated photos passed in full.
- Two negatives were flagged (`cc_absent_12`, `cc_other_object_07`, both asked for a fire hydrant). COCO is thorough
  but not a verified-absence set, so a person should look at these two before calling them model errors.

## Limits

- Slices have 10 to 30 cases, so intervals are wide. The card lists them.
- COCO is a public benchmark that models may have seen in training. It says little about a tray-tag scene.
- One run, one pass. The agent-chosen order was not run on this set.
- Labels are crowd-worker boxes derived from polygons, with no second annotator here.
