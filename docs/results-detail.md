# Result details

This file is the detail appendix for `docs/real-results.md`. That file is the one home for results: it lists the three real results, their run ids, gate decisions and free re-read commands. The tables and notes below keep the full per-condition detail behind those summaries. Small samples here are not a benchmark or a safety approval, and no model graded anything.

## Contents

- COCO val2017 photos, run `a165cd6773cd433a`
- Open Images everyday red coloured objects, runs `6459e3b33ccf427e` and `cdd877484c9f4fac`
- Harder Open Images photos, run `af594b603e0149d9`, and DAVIS 2017 video frames, run `8f6003378706480a`

## COCO val2017 photos, detail

Run `a165cd6773cd433a`, 2026-11-01. SAM 3.1 through the Meta Model API, 132 cases in a fixed order (mock
planner, so the order is scripted and not agent-chosen). Cost about $0.33. Source label `LIVE_META` on every step.

### Labels

COCO annotators drew a polygon around every instance of fire hydrant, stop sign and traffic light. The human box
is the tight rectangle of that polygon. Each positive photo has exactly one non-crowd instance. A negative photo
is one where COCO has no annotation of the requested class. Nothing was labeled by SAM or Muse. The fetcher is
`scripts/fetch_coco.py` (seed 17) and the polygons are kept for mask scoring.

### Result

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

### What it shows

- Low light is the weakest slice: 4 of 10 failed, three of them with nothing returned.
- Small objects failed 5 of 24, mostly traffic lights and stop signs that were missed.
- Normal and truncated photos passed in full.
- Two negatives were flagged (`cc_absent_12`, `cc_other_object_07`, both asked for a fire hydrant). COCO is thorough
  but not a verified-absence set, so a person should look at these two before calling them model errors.

### Limits

- Slices have 10 to 30 cases, so intervals are wide. The card lists them.
- COCO is a public benchmark that models may have seen in training. It says little about a tray scene.
- One run, one pass. The agent-chosen order was not run on this set.
- Labels are crowd-worker boxes derived from polygons, with no second annotator here.

## Open Images everyday red coloured objects, detail

Run on 2026-10-31 through the Meta Model API (Standard mode). Every number below comes from a saved
report in `artifacts/runs/`. Python scored every case. Nobody graded by eye, and no model graded.

### Set up

- Photos: 24 from Open Images V7 (validation and test splits), CC BY 2.0, each with its own author and
  landing page recorded in the manifest. Built by `scripts/fetch_open_data.py` with seed 7.
- Task: segment a fire hydrant or a stop sign. The prompt is the class name.
- Labels: boxes drawn or verified by Open Images annotators. Absent cases are images where annotators
  verified the class is not there. No label came from SAM or Muse.
- Pass: best box overlap (IoU) of at least 0.35, or no detection on an absent photo.
- Agent: Muse Spark 1.3 picked each test by function calling. SAM 3.1 segmented. Run 6459e3b33ccf427e.

### Main result

After adjudication: 20 of 22 scored cases passed (95 percent Wilson interval 72% to 98%), with 2 cases
marked unknown. Run cdd877484c9f4fac covers all 24 cases. SAM answers were replayed from the cache of
the first run (6459e3b33ccf427e), so no new SAM call was made.

Before adjudication the same photos scored 20 of 24 (64% to 93%). Both numbers are kept here on
purpose. The two removed cases were doubtful labels, not model passes, and the first run is saved
unchanged.

Adjudication record: on 2026-10-31 the project owner told the assistant to mark `oi_normal_03` and
`oi_low_light_04` unknown. The assistant had looked at both photos. There was no second annotator, so
this is one person's call and not an independent review. The original labels, the reason and the
decision are stored in each case's `label_provenance.adjudication`.

| Slice | Passed of scored | 95% interval | Note |
| --- | --- | --- | --- |
| normal | 5 of 5 | 57% to 100% | 1 case marked unknown |
| low light | 3 of 3 | 44% to 100% | underpowered, 1 case marked unknown |
| truncated (object cut by the edge) | 4 of 4 | 51% to 100% | underpowered |
| occlusion | 2 of 2 | 34% to 100% | underpowered |
| small object | 2 of 2 | 34% to 100% | underpowered |
| absent (false alarms) | 4 of 6 | 30% to 90% | the only real failures |

Where it passed, the best box overlap was high, from 0.79 to 0.998. The mask followed the object
outline on a real photo in the browser (normal case 1, IoU 0.988).

### The four failures, looked at one by one

| Case | What the photo shows | What it means |
| --- | --- | --- |
| absent 01 | A "NEW ROAD LAYOUT AHEAD" road sign | A real false positive: SAM boxed a road sign as a stop sign |
| absent 02 | A metal object that looks like a teapot sculpture | A real false positive: SAM boxed it as a fire hydrant |
| low light 04 | A pink and blue pipe assembly labeled fire hydrant | Doubtful label. The photo is not dark, only the grass is, so the condition tag is also weak |
| normal 03 | A red street fire-alarm call box labeled fire hydrant | Probably a label error. SAM finding no hydrant may be right |

The last two were marked unknown with `python -m blindspot_ci.cli adjudicate` (see the record above).
That leaves the two false positives as the only model failures in the scored set.

What the failures suggest, as hypotheses and not findings: SAM 3.1 is strong when a real object is
there, and weaker at saying no on look-alikes (a road sign, a metal object). Six absent photos cannot
confirm that.

### Stress tests

- Measured corruptions (run c85d2c55664044c2): 5 passing normal photos, each degraded by low light,
  blur, JPEG and contrast at severities 3 and 5. Muse chose to stop after 22 of the 40 variants. All 22
  passed, including severity 5. This means no failure was found in the 22 tested, not that the other 18
  would pass. The interval for 22 of 22 is roughly 85% to 100%.
- Muse Image variants: only run on the synthetic drawings, where SAM found nothing. Not evidence.

### Did the agent beat random order?

No evidence it did. On a run of 8 tests (run f48fd1b4e15f442c) the agent found 1 of the 4 failures,
where a random order is expected to find 1.33. Its first failure came at test 7, where random order
expects 5. The chance of a random order doing as well is 0.83. With 24 cases this cannot separate
skill from luck either way. The value of the tool today is the evidence pipeline: labeled data, scoring,
intervals, the card and the audit.

### Limits

- This is public photos of hydrants and stop signs, not a maintenance tray tag.
- Counts are small. Quote counts with their interval, never a bare percentage.
- Open Images labels are not perfect. Two of 24 were found doubtful and adjudicated by one person. The
  other 22 have not been reviewed a second time (0 of 24 have a named independent reviewer).
- Condition tags are measured by rule (mean brightness, annotator flags, box size) and fixed before
  the run. They were not tuned after seeing results, so low light 04 stays as tagged.
- Results hold for sam-3.1 through the Meta Model API on this date.
- A pass is not a safety approval.

### Reproduce

```powershell
python -I scripts/fetch_open_data.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_openimages\open-labels.json" --dataset open
$env:BLINDSPOT_MAX_CALLS = "60"
.\scripts\live_experiment.ps1 -Dataset open -Steps 24
python -m blindspot_ci.cli card --run <run id>
```

Cost: the six saved run reports sum to $0.32, plus a few cents for audits. About $0.35 in total.

## Harder photos and DAVIS video frames, detail

Both runs use SAM 3.1 live. The test order came from the scripted mock planner so that every case was
scored once. The Muse Spark agent did not choose these tests, so these runs say nothing about the
agent. Labels come from people (Open Images annotators, DAVIS annotators), never from SAM or Muse.

### Hard tier (Open Images V7), run af594b603e0149d9

Rules were fixed in `scripts/fetch_open_data_hard.py` before any model saw an image. The set excludes
every photo from the first Open Images set. Low light is measured on the object, not the whole photo.

- Target was about 50 cases. Only 21 were built: most candidate Flickr links are dead (HTTP errors), so
  the quotas for truncated, hard negative and absent were not met.
- 20 of 21 passed. By condition: normal 6 of 6, look-alike scene 5 of 5, truncated 2 of 2, absent 2 of 2,
  hard negative 1 of 1, low light 4 of 5.
- One failure: hd_low_light_01, a dark traffic light, best box overlap 0.29 (threshold 0.35).
- Only one hard negative (a road sign scene with no stop sign) survived, so how SAM handles look-alikes
  is not tested well here. The first set had two real false positives, which this set could not repeat.

### Real video frames (DAVIS 2017), run 8f6003378706480a

14 clips, 8 evenly spaced frames each, 112 frames. DAVIS annotators drew a pixel mask on every frame.
The box is the tight rectangle around that mask. The text concept (bear, boat, car, and so on) comes
from the clip name. Only the chosen frames were read from the 833 MB zip with HTTP range requests.

- 111 of 112 passed. By condition: normal 75 of 75, low light 16 of 16, truncated 13 of 13, small
  object 7 of 8.
- One failure: dv_soccerball_f020, a soccer ball about 105 by 86 pixels, SAM returned nothing.
- 13 of 14 clips passed on every sampled frame.

Limits to state out loud:
- Frames from one clip are strongly correlated. The honest sample size is about 14 clips, not 112, so
  the Wilson interval on 112 frames is too narrow.
- The hosted API takes one image per call. This tests frames of real video. It tests no tracking and no
  temporal model.
- DAVIS objects are large, salient animals, cars and people. No frame had the object out of view, so the
  absent case is untested here.
- DAVIS data is for research use. Frames stay out of git and out of the ZIP, and the script rebuilds them.

### Video with the Muse Spark agent choosing tests, run 6c741b6c6304480b

The agent saw the 112 frames (labels hidden) and picked tests by function calling. It stopped after
20 tests and all 20 passed. Its planner calls were live. The SAM answers were replayed from the live
run above (tagged CACHE_LIVE_META), so they are real SAM 3.1 results but not new calls. Estimated cost
$0.063, which is the planner calls.

- It noticed that boat frames score lower than the rest (overlap about 0.70 to 0.75 against 0.95 or
  more) and probed four boat frames. All four stayed above the 0.35 threshold.
- It never picked dv_soccerball_f020, the one frame that failed in the full run, and it found no
  failure. This run gives no evidence that it finds failures better than random, and the earlier
  comparison on Open Images found none either.
- The boat clip is the weakest result in the video set. It is a lead for a person to check, not a failure.

### Mask quality on the video frames (no new model calls)

The box test says whether SAM found the object. This scores the outline itself. DAVIS annotators drew a
pixel mask on every frame, so `scripts/eval_masks.py` rasterizes the saved SAM masks and compares them
with those human masks (Jaccard index J, the measure of Perazzi et al. 2016). It reads the saved run
`8f6003378706480a`, so it costs nothing.

- Mean J 0.926, median 0.955. 111 of 112 frames (99%) reach J of 0.5 or better and 109 (97%) reach 0.75.
- By condition: normal 0.93, low light 0.95, truncated 0.93, small object 0.82.
- By clip, lowest first: boat 0.79, soccer ball 0.82, duck in flight 0.86, goat 0.92. The rest are 0.93 to 0.98.
- Worst frames: the soccer ball frame where nothing was returned (J 0), one duck frame at 0.68, then boat frames at 0.75 to 0.81.
- This agrees with the box result and the agent's hunch: boats are the weak spot. They pass the box test but the outline is looser.
- Limits: frames of one clip are correlated, so treat this as 14 clips. DAVIS objects are large and salient. The J
  score uses the detection whose box best matches the human box. Results are in `artifacts/mask-eval-8f6003378706480a.json`.

### Cost

Hard run $0.05, video run $0.28, agent video run $0.06, Wonder audits and cards about $0.09. Cards are in artifacts and each
audit is saved next to its run.

### Reproduce

```powershell
python -I scripts/fetch_open_data_hard.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_openimages\hard-labels.json" --dataset hard
python -I scripts/fetch_open_video.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_davis\video-labels.json" --dataset video
$env:BLINDSPOT_PROVIDER="meta"; $env:LIVE_API_ENABLED="true"; $env:BLINDSPOT_DATASET="video"; $env:BLINDSPOT_MAX_CALLS="150"
python -m blindspot_ci.cli experiment --steps 112 --planner mock
```
