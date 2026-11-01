# Real results

Three real SAM 3.1 results exist. Each is scored by plain Python against human labels. No model graded
anything. These are small samples and are not a benchmark or a safety approval.

| | COCO photos | DAVIS video frames | Long video (MOT20-03) |
| --- | --- | --- | --- |
| Run id | `a165cd6773cd433a` | `8f6003378706480a` | `8c351fcde7154e21` (first scoring, wrong), `e30e0efcc7ca43a7` (corrected) |
| Date | run file starts 2026-10-31 22:02 UTC | run file starts 2026-10-31 13:00 UTC | 2026-11-01 |
| Mode | LIVE_META | LIVE_META | one paid streaming call, then re-scored from the saved raw text |
| Test order | scripted (planner MOCK_POLICY) | scripted (planner MOCK_POLICY) | box prompts on 16 people |
| Gate decision | NO_GO | NEEDS_REVIEW | NO_GO with `fixtures/policies/long-video.json` |

The COCO and DAVIS dates in the run files are in UTC, so local dates may differ by a day. Other docs say
Nov 1 for COCO.

## COCO val2017 photos

- 132 cases of fire hydrants, stop signs and traffic lights. Low light found 6 of 10. Small objects 19 of 24.
  The bar is 9 of 10.
- IoU sweep: low light 6 of 10 holds up to a bar of 0.50 and falls to 4 of 10 at 0.75. Small objects fall
  further below the bar at 0.75.
- Slice tests: low light 6 of 10 against 113 of 122 for the rest has p 0.0087 raw and 0.0612 after Holm
  correction, so the label is not distinguishable from chance.
- Caveats: one run, 10 to 30 cases per condition, COCO may have been seen in training (unknown), and photo
  licensing is not yet confirmed for public display. See `docs/results-coco.md`.

## DAVIS 2017 video frames

- 112 frames from 14 clips. Decision NEEDS_REVIEW.
- DAVIS is likely seen by SAM in training. This is UNVERIFIED, from summaries of the SAM 2 and SAM 3 papers.
  Check https://arxiv.org/abs/2408.00714 and https://arxiv.org/abs/2511.16719 before quoting it.
- Caveats: frames of one clip are correlated, so treat it as 14 clips. See `docs/results-hard-and-video.md`.

## Real long video test

- Public MOT20-03 crowd video, 2,405 frames, 16 people tracked from human box prompts, one paid streaming call.
  Spend for the whole test was at most 0.48 US dollars.
- The service shrank the 1173 by 880 clip to 586 by 440 and returned boxes at that size. The first scoring
  compared mismatched sizes and wrongly showed 0 of 16. The fix scales the boxes before scoring, and the raw
  paid text was re-scored for free.
- Corrected result: 3 of 16 people followed correctly on at least 90 percent of their scored frames. The median
  person was followed on 82.5 percent. Seed frames 16 of 16.
- Most failures were a box returned with weak overlap (about 2,100 frames), not a missing target (178 frames).
- The stream was cut off at frame 2351 of 2405, so 108 labeled frames count as errors, not misses.
- Gate: NO_GO. Occluded 40 of 102, dark 32 of 48.
- Caveats: human boxes include hidden parts, the camera is not fixed, one sequence and 16 people only, and the
  intervals overstate certainty because frames are correlated. MOT20 is CC BY-NC-SA 3.0 non-commercial data and
  is not stored in this repository. MOT20-02 and MOT20-05 were not run because their 76 and 86 MB uploads hung.

## Re-read the saved runs for free

The COCO and DAVIS run files are committed in `fixtures/examples`. These commands make no model call.

```powershell
$env:BLINDSPOT_RUNS_DIR = "fixtures/examples"
python -m blindspot_ci.cli release-gate --run a165cd6773cd433a
python -m blindspot_ci.cli iou-sweep --run a165cd6773cd433a
python -m blindspot_ci.cli slice-tests --run a165cd6773cd433a
python -m blindspot_ci.cli release-gate --run 8f6003378706480a
```

The long video run files are kept locally in `artifacts/runs` and are not committed, because the data is
non-commercial. On a machine that has them, read them with the default runs folder:

```powershell
Remove-Item Env:BLINDSPOT_RUNS_DIR
python -m blindspot_ci.cli temporal-report --run e30e0efcc7ca43a7
python -m blindspot_ci.cli release-gate --run e30e0efcc7ca43a7 --policy fixtures/policies/long-video.json
```

To rebuild them, follow `docs/long-video-test.md`: fetch the labels, build the manifest, and replay the saved
raw stream with `--from-raw`. Re-scoring needs both the manifest and the raw stream. Without the raw stream
the only way to get a new result is a new paid call.

Unverified in this document: the corrected run file `e30e0efcc7ca43a7` was not found in the local artifacts
folder when this was written, so the long video numbers come from the owner's report, not from a re-read.
