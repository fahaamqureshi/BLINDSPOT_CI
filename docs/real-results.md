# Real results

Three real SAM 3.1 results exist. Each is scored by plain Python against human labels. No model graded
anything. These are small samples and are not a benchmark or a safety approval.

| | COCO photos | DAVIS video frames | Long video (MOT20-03) |
| --- | --- | --- | --- |
| Run id | `a165cd6773cd433a` | `8f6003378706480a` | `8c351fcde7154e21` (first scoring, wrong), `e30e0efcc7ca43a7` (corrected, reported); `e1e1878e28614c7e` (rebuilt on 2026-11-02) |
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
  licensing is not yet confirmed for public display. See `docs/results-detail.md`.

## DAVIS 2017 video frames

- 112 frames from 14 clips. Decision NEEDS_REVIEW.
- DAVIS is likely seen by SAM in training. This is UNVERIFIED, from summaries of the SAM 2 and SAM 3 papers.
  Check https://arxiv.org/abs/2408.00714 and https://arxiv.org/abs/2511.16719 before quoting it.
- Caveats: frames of one clip are correlated, so treat it as 14 clips. See `docs/results-detail.md`.

## Real long video test

- Public MOT20-03 crowd video, 2,405 frames, 16 people tracked from human box prompts, one paid streaming call.
  The plan prices the one call at 0.481 US dollars, and the replays cost nothing.
- The service shrank the 1173 by 880 clip to 586 by 440 and returned boxes at that size. The first scoring
  compared mismatched sizes and wrongly showed 0 of 16. The fix scales the boxes before scoring, and the raw
  paid text was re-scored for free.
- Corrected result: 3 of 16 people followed correctly on at least 90 percent of their scored frames. The median
  person was followed on 82.5 percent. Seed frames 16 of 16.
- Most failures were a box returned with weak overlap (about 2,100 frames), not a missing target (178 frames).
- The stream was cut off at frame 2351 of 2405, so 108 labeled frames count as errors, not misses.
- Gate: NO_GO. Occluded 40 of 102, dark 32 of 48. The rebuild also shows small objects 171 of 179 and
  truncated 12 of 12. Details of the rebuild are at the end of this file.
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
non-commercial. After rebuilding (see below), read the run with its new id. A replay can also write to a
scratch folder through `BLINDSPOT_RUNS_DIR`:

```powershell
Remove-Item Env:BLINDSPOT_RUNS_DIR
python -m blindspot_ci.cli temporal-report --run <rebuilt run id>
python -m blindspot_ci.cli release-gate --run <rebuilt run id> --policy fixtures/policies/long-video.json
```

To rebuild them, follow `docs/long-video-test.md`: fetch the labels, build the manifest, and replay the saved
raw stream with `--from-raw`. Re-scoring needs both the manifest and the raw stream. Without the raw stream
the only way to get a new result is a new paid call.

## Rebuild check (2026-11-02)

The corrected run file `e30e0efcc7ca43a7` is not on disk, but its inputs are. The raw paid stream
`artifacts/video-raw/2892e250d09944eb-MOT20-03.txt` and a MOT20 manifest were replayed with no key and no
network, into a scratch folder, with `long-video --from-raw`. A replay always gets a new id, here
`e1e1878e28614c7e`, so the id `e30e0efcc7ca43a7` cannot be reproduced. Its numbers were. Re-read with
`temporal-report` and with `release-gate --policy fixtures/policies/long-video.json`:

- 3 of 16 people followed on at least 90 percent of scored frames, median 82.5 percent, none held the whole clip.
- Failed scored frames 2,288: box returned but below the overlap bar 2,110, target not returned 178.
- Seed frames passed 16 of 16. Boxes were scaled from 586 by 440 to 1173 by 880 before scoring.
- 108 labeled frames from frame 2352 to 2405 count as errors, not misses.
- Gate NO_GO. Occluded 40 of 102, dark 32 of 48, small object 171 of 179, truncated 12 of 12 (only 12 scored).
- By-clip intervals appear for dark, occluded and small object. Occluded is 0.236 to 0.549 by clip.

The 0.481 dollars is the plan's exact price for the one paid call, from `long-video --dry-run`, not a bill.
