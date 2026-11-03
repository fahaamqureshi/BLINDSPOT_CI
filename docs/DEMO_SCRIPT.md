# Demo script: Find the Hidden Failure, Red Safety Tag Inspection

## Current local demo and backup

Open http://127.0.0.1:8000, choose Try a practice check, keep Practice drawings selected, and click Run check. Show DEMO_ONLY, inspect the low-light failure in Test evidence, inspect the recorded decision order under Technical details, add a typed reviewer note, and download the Markdown report. These are explicitly scripted answers. The local submission-walkthrough.webm under artifacts/submission-audit is a recording of this actual workflow with repository-owned synthetic assets; it has not been uploaded or submitted.

For saved real tracking evidence, use the local replay described in REAL_WORLD_VIDEO_DEMO.md. It contains non-commercial third-party footage and is excluded from the submission package. Do not publish it without confirming the applicable contest and asset terms. The earlier five-model report is also saved evidence, not a live call during playback. The standard importer now uses zero-based API indexes and excludes seed frames; regenerate older manifests before new inference.

## Verified mock route, 2026-11-03

Recommended 2 to 3 minute no-cost route for this audit. The historical storyboard below includes live claims not reproduced in this audit. Confirm private portal video rules before recording.

1. First 20 seconds: Open Home. Select Low light in the practice preview to see the deliberate fixture miss, then Obstructed to see the unknown case. Disclose that these are synthetic drawings and scripted answers, not a live model result. Explain that real evaluations use labels from a person.
2. Next 30 seconds: Open Workspace, select Practice drawings, up to five tests and Run check in the visible settings panel. Disclose scripted fixtures and synthetic drawings.
3. Next 45 seconds: Show Practice data only and DEMO_ONLY. Select Test evidence: normal PASS, low-light deliberate miss, alternate view PASS, occluded UNKNOWN and absent PASS. The alternate view is an existing image, not a repaired model or camera movement.
4. Next 30 seconds: Open Technical details for source, hashes and order. Explain that optional Muse selects, SAM predicts in live mode, Python scores and the gate checks evidence. This mock run proves no live intelligence.
5. Last 25 seconds: Download report and show run ID/source. State blockers: owner photos, independent labels, live validation and private rules. A person decides every release.

Before presenting, run python scripts/audit_mock.py and python scripts/check.py. Do not imply browser project creation, photo upload or a nine-tool trace viewer were demonstrated.

Running time: about 5 minutes with questions, 90 seconds in the short form at the end. Rule for the whole demo: never show a MOCK_FIXTURE number as a SAM result. Say out loud which steps are live evidence and which steps are fixture practice. The red safety tag owner dataset does not exist yet, so this script never fakes a tray failure. It shows the shipped synthetic tag fixture as practice, then proves the hidden-failure idea on the committed COCO and DAVIS live runs.

## Setup (before anyone is watching)

- Start the app in mock mode: `python -m blindspot_ci.cli serve`, then open http://127.0.0.1:8000/app
- Confirm the health route answers and the examples list loads. Both were verified in this audit; see `docs/TEST_RESULTS.md`.
- Open two tabs: the app with the synthetic dataset, and the app with the saved COCO run (run id a165cd6773cd433a, dataset coco). Keep the DAVIS run id 8f6003378706480a ready to type.
- Have the free gate commands ready in a terminal with BLINDSPOT_RUNS_DIR set to fixtures/examples. No key, no spend, no network is needed for any step below.
- Have the live agent run record ready to show as text: run a23089bef4a840c8 in `docs/real-results.md`. That run needed a key and live flags, so it cannot be re-run for free in the room. Show the saved record, and say so out loud.

## Act 1. The inspection idea (45 seconds)

Say: A QA engineer must decide whether a vision model is ready to ship. A bright demo photo proves almost nothing. The failures hide in low light, small objects and half-hidden views. BLINDSPOT CI labels cases first, hides the labels, lets SAM 3.1 try, scores with plain Python, and the Release Gate says ship, do not ship, or not enough evidence, with the failing photos attached.

Show the home page verdict words and the four decisions with exit codes. Say: GO_CANDIDATE has never been reached, and this tool is not a safety approval. A person decides.

## Act 2. Fixture practice on the red safety tag (60 seconds, clearly labeled)

Say clearly: This first run is fixture practice. The photos are drawings, the answers are scripted, and the result proves the software runs. It says nothing about SAM.

- In the app, run the experiment on the synthetic dataset (5 cases: normal, low light, occluded marked unknown, alternate view, absent).
- Point at the mode badge: MOCK_FIXTURE. Point at the low light case: the scripted answer misses it on purpose, and the alternate view case is the recovery photo a person supplied. Say: a recovery view is a second photo, not a camera moving.
- Point at the occluded case: labeled unknown, so Python does not score it. Say: unknown is the honest bucket, and the gate punishes a run that hides too much in it.
- Point at the Release Gate panel: DEMO_ONLY. Say: scripted answers can never give any other verdict, however good they look. That refusal is a feature.

If asked for a real tray result, say: No photos of the owner tray tag exist yet. The label tool and importer are ready, the photo plan is in `docs/dataset.md`, and until those photos exist this act stays fixture practice. Do not invent a tray pass count.

## Act 3. The hidden failure on real photos (90 seconds, live evidence)

Say: Now the same pipeline on real photos that a person labeled. These answers are LIVE_META, saved from real SAM 3.1 calls, and re-reading them here costs nothing.

- Open the saved COCO run. Read the verdict first: NO_GO, do not ship yet.
- Read the failing rows: low light found 6 of 10, small objects 19 of 24, against a bar of 9 of 10. Normal photos passed 24 of 24. Say: that gap between the easy slice and the hard slices is the hidden failure. One headline score of 119 of 132 would have hidden it.
- Open one failed low light photo and show the human box beside the empty or misplaced model answer. Say how Python scored it: best box overlap against the human box, bar 0.35.
- Read the fix list from the gate panel: fix the failing low light and small object cases, collect more cases per condition, add a second annotator, and re-run on fresh photos.
- In the terminal, run the free slice test and read one line: low light raw p 0.0087 becomes 0.0612 after Holm correction, so even this gap is not yet distinguishable from chance on its own. Say: the tool reports that against itself. Small samples stay labeled small.

## Act 3b. The live agent investigation (45 seconds, live evidence shown as a saved record)

Say: This is a separate live run, not the headline run you just saw. In run a23089bef4a840c8 the Muse planner chose the test order live with the labels hidden, on six shipped COCO low_light and small_object cases. Six Muse muse-spark-1.3 calls and six SAM sam-3.1 calls, estimated cost 0.033 US dollars against a hard cap of 0.10.

- Read the three misses first: cc_low_light_01, cc_low_light_02 and cc_low_light_04 all scored IoU 0.0, a plain false negative with no box at all. Say: SAM genuinely missed these. Python scored them, not a model.
- Read the planner reaction: after each miss it asked for an alternate view as extra evidence and saved the case as a regression case, then chose the next hard case, varying the concept and moving from low_light to small_object. The passes were cc_low_light_03 at 0.5789, cc_small_object_02 at 0.9323 and cc_small_object_01 at 0.8333.
- Land the separation: the gate on this six case agent run said NEEDS_REVIEW, because six cases are too few to decide a release. The fixed gate on the saved COCO run said NO_GO, low light 6 of 10 and small objects 19 of 24. Say: the agent explores, the fixed gate decides. The agent did not produce the headline results, and the headline runs used a scripted order.

## Act 4. Video frames and the honesty checks (60 seconds, live evidence)

- Open the saved DAVIS run. Verdict NEEDS_REVIEW, 111 of 112 frames passed. Say: that sounds strong, and the gate still refuses a pass, for two stated reasons. There is no absent case at all, and DAVIS may have been seen in SAM training. That overlap note is UNVERIFIED until the owner checks the SAM papers.
- Say: 112 frames are really about 14 clips, because frames from one clip look alike. The gate shows clip-aware intervals where it can and says not available where it cannot, instead of printing a narrow interval it cannot back.
- Optional, if time allows: describe the long video in one breath. One public crowd video, 16 people, one paid call. Only 3 of 16 were followed well, verdict NO_GO. The first scoring wrongly showed 0 of 16 because the service returned smaller boxes; the team fixed the scaling and re-scored the saved answer for free. Say: saved raw answers are why that fix cost nothing.

## Act 5. Close (30 seconds)

Say: What you saw is a release gate, not a new model. Labels from a person, labels hidden during the test, Python as the only judge, a verdict with the failing photos and a fix list, and a gate that calls practice DEMO_ONLY and has never yet said GO_CANDIDATE. Next steps are owner photos taken after the model release, a second labeler, and then a fresh live run. The full checklist is in `docs/SUBMISSION_CHECKLIST.md`.

## 90-second short form

1. Problem (10 seconds): a model can ace a bright demo and still miss dark or small objects.
2. Fixture in one line (10 seconds): the tag drawings show the software running; badge says MOCK_FIXTURE, gate says DEMO_ONLY, nothing here grades SAM.
3. Real verdict (25 seconds): COCO live run, NO_GO. Low light 6 of 10, small objects 19 of 24, normal 24 of 24. Show one failed photo with both boxes.
4. Live agent investigation (20 seconds): separate six case live run a23089bef4a840c8. The Muse planner chose hard low light cases with labels hidden, SAM missed cc_low_light_01, cc_low_light_02 and cc_low_light_04 at IoU 0.0, and after each miss the planner asked for an alternate view, saved a regression case and picked the next hard case. The gate on that small run said NEEDS_REVIEW, and the fixed gate said NO_GO. The agent explores, the fixed gate decides, and the headline runs used a scripted order.
5. Honesty (15 seconds): slice test weakens after correction, DAVIS is NEEDS_REVIEW with a training-overlap warning, samples are small and mostly single-labeler.
6. Next (10 seconds): owner tray photos plus a second labeler, then a fresh live run. Until then GO_CANDIDATE stays out of reach.

## Questions a judge may ask

- Is the agent choosing these tests? In the two saved headline runs, no: they used a scripted order. In the separate six case live run a23089bef4a840c8, yes: the Muse planner chose hard low light and small object cases with labels hidden, found three IoU 0.0 misses, and reacted after each one. That run is NEEDS_REVIEW and underpowered, the fixed gate still decides, and there is no proven benefit over random order yet. Say agent assisted, not fully autonomous.
- Can a model grade itself here? No. Python scores against hidden human boxes. Image, voice and Wonder output never changes a score.
- What stops runaway spend? Budget reserved before each paid call, per-run and server-wide caps, call limits, and a cache keyed by input hash so re-reads are free.
- Is any of this a safety approval? No. The gate advises a person with evidence. GO_CANDIDATE itself says a person still decides.
