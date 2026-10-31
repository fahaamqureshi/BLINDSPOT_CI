# Results: harder photos and real video frames

Both runs use SAM 3.1 live. The test order came from the scripted mock planner so that every case was
scored once. The Muse Spark agent did not choose these tests, so these runs say nothing about the
agent. Labels come from people (Open Images annotators, DAVIS annotators), never from SAM or Muse.

## Hard tier (Open Images V7), run af594b603e0149d9

Rules were fixed in `scripts/fetch_open_data_hard.py` before any model saw an image. The set excludes
every photo from the first Open Images set. Low light is measured on the object, not the whole photo.

- Target was about 50 cases. Only 21 were built: most candidate Flickr links are dead (HTTP errors), so
  the quotas for truncated, hard negative and absent were not met.
- 20 of 21 passed. By condition: normal 6 of 6, look-alike scene 5 of 5, truncated 2 of 2, absent 2 of 2,
  hard negative 1 of 1, low light 4 of 5.
- One failure: hd_low_light_01, a dark traffic light, best box overlap 0.29 (threshold 0.35).
- Only one hard negative (a road sign scene with no stop sign) survived, so how SAM handles look-alikes
  is not tested well here. The first set had two real false positives, which this set could not repeat.

## Real video frames (DAVIS 2017), run 8f6003378706480a

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

## Video with the Muse Spark agent choosing tests, run 6c741b6c6304480b

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

## Mask quality on the video frames (no new model calls)

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

## Cost

Hard run $0.05, video run $0.28, agent video run $0.06, Wonder audits and cards about $0.09. Cards are in artifacts and each
audit is saved next to its run.

## Reproduce

```powershell
python -I scripts/fetch_open_data_hard.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_openimages\hard-labels.json" --dataset hard
python -I scripts/fetch_open_video.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_davis\video-labels.json" --dataset video
$env:BLINDSPOT_PROVIDER="meta"; $env:LIVE_API_ENABLED="true"; $env:BLINDSPOT_DATASET="video"; $env:BLINDSPOT_MAX_CALLS="150"
python -m blindspot_ci.cli experiment --steps 112 --planner mock
```
