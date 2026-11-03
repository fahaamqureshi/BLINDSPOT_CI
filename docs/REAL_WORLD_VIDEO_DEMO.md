# Real-world crowd video demo

Recorded on 2026-11-03. This is a small seeded tracking evaluation, not a benchmark or deployment approval.

## Open the demo

Replay: http://127.0.0.1:8032/demo/

Saved app run: http://127.0.0.1:8032/app?run=3015e3b160ee410d

Complete annotated video: http://127.0.0.1:8032/demo/real-world-demo.mp4

The replay supports playback, frame scrubbing, scene switching, reference and prediction toggles, failure jumps, per-person timelines, saved app inspection and exports. Its saved results do not trigger new paid calls. The served app uses mock settings with live access disabled. Voice, image generation and audit generation are disabled on this replay server. Earlier five-model execution evidence remains linked separately and is not presented as a new test.

If the local server stops, run `.venv/Scripts/python.exe artifacts/real-world-demo/serve.py` from the repository root. This local helper disables dotenv loading and live calls. Do not rerun the paid inference helper to replay results.

## Scenario and source

The task is to follow three specified people through a busy station and a nighttime stadium exit after receiving their starting boxes. It does not evaluate automatic person discovery or identity recognition.

Source: [MOTChallenge MOT20](https://motchallenge.net/data/MOT20/), Patrick Dendorfer and collaborators. Source video URLs are https://motchallenge.net/sequenceVideos/MOT20-01-raw.mp4 and https://motchallenge.net/sequenceVideos/MOT20-03-raw.mp4. Human reference labels came from the official training label archive already cached locally.

The source is licensed under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). Media and derived clips remain in ignored local artifacts for non-commercial research. Source watermarks are retained. They were not committed or redistributed.

| Clip | Duration | Frames | Input size | Source track IDs |
| --- | --- | --- | --- | --- |
| MOT20-01 station | 17.16 seconds | 429 | 960 by 540 | 17, 6, 7 |
| MOT20-03 stadium exit | 20 seconds | 500 | 640 by 480 | 535, 67, 486 |

Selection preceded inference. Eligible tracks had visibility at least 0.7 in the starting frame, a starting box fully within the image, height at least 30 pixels, and at least 100 subsequent annotated frames with visibility above 0.2. Candidates were sorted by starting box height and track ID; the smallest, middle and largest entries were selected. The preparation script and manifest preserve this rule.

The source labels are one-based. Video frame zero maps to source annotation one. Seed frame zero is excluded. Unlabeled frames and visibility at or below 0.2 are not scored. Starting prompt boxes use inclusive endpoints. Reference boxes remain unchanged apart from resizing to the clip coordinates. Returned model boxes are mapped from their declared frame size to the clip size before scoring. No model supplies reference labels.

## Observed results

Run ID: `3015e3b160ee410d`. Two fresh SAM 3.1 streaming calls returned all 929 requested frames. No retries, request errors or malformed frame records were observed. Reported processing times were 63.914 and 59.741 seconds. Provider usage reported 429 and 500 processed frames. Estimated cost was USD 0.1858, within the user's existing USD 30 authorization. This is an estimate from recorded usage, not an invoice.

All-frame scoring used IoU at least 0.35. There were 1,863 eligible target-frame checks: 1,391 passed, 430 had insufficient overlap and 42 had no returned target. Another 918 target-frame slots were unscored. Six starting-frame slots were excluded. Combined retention was 74.7 percent. The median per-person retention was 72.2 percent.

| Scene and track | Correct / eligible | Retention |
| --- | --- | --- |
| Station 17 | 197 / 346 | 56.9 percent |
| Station 6 | 232 / 232 | 100 percent |
| Station 7 | 313 / 347 | 90.2 percent |
| Stadium 535 | 44 / 114 | 38.6 percent |
| Stadium 67 | 389 / 499 | 78.0 percent |
| Stadium 486 | 216 / 325 | 66.5 percent |

Two of six people reached 90 percent retention on their eligible frames. A person leaving the annotated scene is unscored after departure; passing every eligible frame does not mean tracking throughout the full video.

The saved app report samples one eligible frame per target every 25 frames, according to a fixed rule: 73 sampled checks, 54 pass and 19 fail. Its 36 distinct frame thumbnails have actual file hashes. Configured case IDs match the sampling rule applied to the pre-inference human manifest. The replay table and annotated video use all eligible frames instead of this sample.

The default app photo policy returns NEEDS_REVIEW. The repository's existing `fixtures/policies/long-video.json` returns NO_GO because occluded cases pass only 26 of 42 sampled checks, below its 90 percent bar. Neither policy was weakened. Both decisions are saved and explained separately on the replay page.

## Validation evidence

All 1,863 eligible scores were independently recomputed from saved raw model boxes and human references, without calling the application scorer, and matched. All 73 saved step image references were fetched and their hashes verified. Landing, app, run JSON, gate, export, replay and both media URLs returned HTTP 200. A note entered through the app persisted in its reviewer sidecar.

Browser checks covered station playback, stadium playback, failure jumps, scene switching, actual frame evidence and reviewer note saving. No browser console errors were observed. The replay had no horizontal overflow at 390 by 844. Screenshots, the browser walkthrough recording, data and HTTP checks are local under `artifacts/real-world-demo/`. The full 37.16-second annotated MP4 is under `artifacts/real-world-demo/public/real-world-demo.mp4`.

The completion gate's exact output is stored in `artifacts/real-world-demo/check-output.txt`. The required command is `.venv/Scripts/python.exe scripts/check.py`, with dotenv disabled, mock provider, heuristic planner and live access false.

## Scoped changes and open issues

Changed source files: `blindspot_ci/experiment/temporal.py` and `tests/test_temporal.py`. The temporal scorer now compares full-precision overlap with the threshold. The new regression case demonstrates that rounding 3499/10001 to four decimals could incorrectly pass a threshold of 0.34988. Temporal report wording now refers to eligible frames and selected clips rather than implying uninterrupted full-clip tracking or making a general camera claim. This document records the local demo; media and local helper scripts remain ignored artifacts.

Limits: six tracks and two scenes cannot establish general accuracy. Frames are correlated, training overlap is unknown, there is no independent second annotation, and full-body human boxes can disagree with visible-content SAM boxes during occlusion. The app's main settings remain photo-oriented; this local video replay bridges into the saved app workflow. The generic temporal report's recovery summaries can bridge unscored gaps, so use individual scored-frame timelines for exact continuity judgments. These limits are not repaired by additional API spending.

Branch: `codex/real-world-video-demo`. The final response records the resulting commit SHA. No push or merge was performed.
