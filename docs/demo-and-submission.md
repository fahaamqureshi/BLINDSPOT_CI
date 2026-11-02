# Demo and submission

This file is the short aligned copy. The primary word for word demo is `docs/DEMO_SCRIPT.md`, titled Find the Hidden Failure, Red Safety Tag Inspection, in a 5 minute form with questions and a 90 second short form. If this file and that script ever disagree, the demo script wins and this file must be fixed. The full merged submission list is `docs/SUBMISSION_CHECKLIST.md`. This file keeps the 90 second flow, the judge reproduction steps and the short checklist in one place so a judge can follow them without hunting.

Rule for the whole demo: never show a `MOCK_FIXTURE` number as a SAM result. Say out loud which steps are simulated, which steps are live evidence and which step is documented only. The red safety tag owner dataset does not exist yet, so the demo never fakes a tray failure.

## Before anyone is watching

- Start the app in mock mode with `python -m blindspot_ci.cli serve`, then open http://127.0.0.1:8000/app in the browser. Mock mode needs no key, no spend and no network.
- Confirm the health route answers at http://127.0.0.1:8000/health and the examples list loads. The home page is at the root path, the full result page is at `/app` and the plain explanation is at `/guide`.
- Keep two saved runs ready: COCO run `a165cd6773cd433a` at `/app?run=a165cd6773cd433a` and DAVIS run `8f6003378706480a`. Both are committed in `fixtures/examples` and re-reading them costs nothing.
- Keep a terminal ready for the free gate commands with `BLINDSPOT_RUNS_DIR` set to `fixtures/examples`. Use that setting only for reading the saved runs. New practice runs write to the default `artifacts/runs` folder, so unset the variable again before running an experiment or starting the server for a new check.

## The 90 second demo, aligned with the demo script

The five beats below are the short form at the end of `docs/DEMO_SCRIPT.md`, with the same order and the same counts. Total time is 90 seconds.

1. Problem and the three jobs (10 seconds, inside the first 15). Say: A vision model can ace a bright demo photo and still miss dark, small or half hidden objects. BLINDSPOT CI labels cases first and hides the labels. Muse Spark decides which test runs next, SAM 3.1 detects the object in the photo, and plain Python verifies the answer against the human box and gives the verdict. A person still decides every release, and this tool is not a safety approval. Say plainly that the two saved headline runs used a scripted test order, so the honest claim today is agent assisted, not fully autonomous.
2. Fixture practice, labelled simulated (10 seconds). Say clearly: This step is simulated. In the app, run the experiment on the synthetic red safety tag dataset with 5 cases: normal, low light, occluded marked unknown, alternate view and absent. The photos are drawings and the answers are scripted. Point at the mode badge `MOCK_FIXTURE` and at the Release Gate panel verdict DEMO_ONLY. Say: scripted answers can never give any other verdict, however good they look, and this step proves the software runs and says nothing about SAM. The occluded case is labelled unknown, so Python does not score it. If asked for a real tray result, say no photos of the owner tray tag exist yet and do not invent a tray pass count.
3. Real verdict on everyday photos (30 seconds, live evidence). Open the saved COCO run `a165cd6773cd433a`. The answers are `LIVE_META`, saved from real SAM 3.1 calls, and re-reading them here costs nothing. Read the verdict first: NO_GO, do not ship yet. Then read the failing rows: low light found 6 of 10 and small objects 19 of 24, against a bar of 9 of 10, while normal photos passed 24 of 24. Say: that gap between the easy slice and the hard slices is the hidden failure, and one headline score of 119 of 132 would have hidden it. Open one failed low light photo and show the human box beside the empty or misplaced model answer. Python scored it by best box overlap against the human box with a bar of 0.35. Then read the fix list in the gate panel: fix the failing low light and small object cases, collect more cases per condition, add a second annotator and re-run on fresh photos.
4. Honesty checks (20 seconds, live evidence plus one documented result). Say: the tool reports against itself. In the terminal, the free slice test shows low light raw p 0.0087 becomes 0.0612 after Holm correction, so even this gap is not yet distinguishable from chance on its own, and small samples stay labelled small. Open the saved DAVIS run `8f6003378706480a`: verdict NEEDS_REVIEW with 111 of 112 frames passed, and the gate still refuses a pass because there is no absent case at all and DAVIS may have been seen in SAM training, which is UNVERIFIED until the owner checks the SAM papers. Say: 112 frames are really about 14 clips, because frames from one clip look alike, and the gate says by clip not available where it cannot back an interval instead of printing a narrow one. The long crowd video belongs in this beat as words only: one public MOT20-03 video, 16 people, one paid call, only 3 of 16 followed well and verdict NO_GO, after a box scaling fix was re-scored from the saved answer for free. That result is documented in `docs/real-results.md` and `docs/long-video-test.md`. It cannot be re-run from the shipped fixtures, because the manifest and the raw stream are owner local inputs kept out of git under the MOT20 licence, so never present it as a step a judge can click or a command a judge can run.
5. What comes next (20 seconds). Say: what you saw is a release gate, not a new model. Labels from a person, labels hidden during the test, Python as the only judge, a verdict with the failing photos and a fix list, and a gate that calls practice DEMO_ONLY and has never yet said GO_CANDIDATE. Next steps are owner photos of the red safety tag taken after the model release, a second labeler for at least 30 percent of cases, and then a fresh live run. Until the owner photos exist, GO_CANDIDATE stays out of reach.

## How the three jobs fit

- Muse Spark 1.3 is the optional agent planner. It picks the next test by function calling and never sees the labels. It is implemented and validated, but the saved COCO and DAVIS headline runs used the scripted `MOCK_POLICY` order, and there is no proven benefit over random order yet. Say agent assisted, not fully autonomous.
- SAM 3.1 is the model under test. It returns boxes and masks for the concept in each photo or frame. Only its saved `LIVE_META` answers count as live evidence.
- Plain Python is the only judge. It scores best box overlap at a bar of 0.35, builds the counts and intervals, and the Release Gate turns one saved run into GO_CANDIDATE, NO_GO, NEEDS_REVIEW or DEMO_ONLY with exit codes 0, 1, 2 and 3. Exit code 4 means a file could not be read. Muse Image, Muse Voice and Muse Wonder output never changes a score.
- A model can never grade itself here. The planner and the browser see the public case only, and ground truth is attached to a step only after scoring. Spend is reserved before each paid call with per run and server wide caps, and re-reads of saved answers are free.

## Judge reproduction from a fresh clone, offline with no key

Every step below uses only shipped fixtures and mock mode. No key, no live flag and no network call is needed after the clone and install. These steps were run on the tree that this file ships with, and the expected results are the ones the commands printed.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/check.py
```

Expected: the gate prints five PASS lines for ruff, pytest, docs style, attribution and secrets, then `Summary: PASS`. Python 3.11 or newer works. Mock results prove the code runs and say nothing about SAM.

Read the two saved live runs for free. Expected decisions and exit codes are part of the check, so a NO_GO exit code of 1 and a NEEDS_REVIEW exit code of 2 are successes here, not failures:

```powershell
$env:BLINDSPOT_RUNS_DIR = "fixtures/examples"
python -m blindspot_ci.cli release-gate --run a165cd6773cd433a
python -m blindspot_ci.cli release-gate --run 8f6003378706480a
python -m blindspot_ci.cli iou-sweep --run a165cd6773cd433a
python -m blindspot_ci.cli slice-tests --run a165cd6773cd433a
```

Expected: COCO decision NO_GO with low light 6 of 10 and small object 19 of 24 below the 0.90 bar. DAVIS decision NEEDS_REVIEW with 111 of 112 passed, absent 0 scored and training overlap marked likely seen as UNVERIFIED. The sweep rescores 73 box pairs and low light stays 6 of 10 at bars 0.25, 0.35 and 0.50. The slice test shows low light p 0.0087 raw and 0.0612 after Holm correction with the label not distinguishable. The evaluation card can also be written for free with `python -m blindspot_ci.cli card --run a165cd6773cd433a` while the same variable is set.

Check coverage and run the labelled simulated fixture. Unset the runs variable first so the new practice run writes to the default folder:

```powershell
Remove-Item Env:BLINDSPOT_RUNS_DIR
python -m blindspot_ci.cli coverage
python -m blindspot_ci.cli experiment --steps 5
python -m blindspot_ci.cli release-gate --run <printed run id>
```

Expected: coverage loads only the synthetic dataset with 5 cases and reports the private and open manifests as unavailable, which confirms they are correctly absent from git. The experiment prints mode `MOCK_FIXTURE` with the low light scripted miss, the occluded case UNKNOWN and no errors. Gating the printed run id gives DEMO_ONLY with exit code 3 and the reason that mock or fixture output is not model performance.

Serve the app and open the three judge pages at desktop width:

```powershell
python -m blindspot_ci.cli serve
```

Open http://127.0.0.1:8000/ for the home verdict, http://127.0.0.1:8000/app?run=a165cd6773cd433a for the COCO NO_GO verdict with its failing rows and fix list, and http://127.0.0.1:8000/guide for the plain explanation. The saved examples answer even without the fixtures variable, because the app falls back to the committed examples for a run it does not hold locally. COCO and DAVIS photos are not in this download, so each failed photo shows the human box and the model box drawn on a blank panel with the words Photo not in this download. That fallback is the honest behaviour. The 5 synthetic drawings do load as photos. Running a new check in the app in mock mode makes practice data only and the warning on the page says so.

Build and inspect the submission package:

```powershell
python scripts/package.py
```

Expected: the script refuses to package if a secret like string is found, and otherwise writes one ZIP under `dist` with an allowlisted file list. Confirm by listing the ZIP: it holds the package code, tests, docs, fixtures with both saved example runs, the long video policy, the synthetic manifest and the 5 sample drawings, plus README, LICENSE, `pyproject.toml`, `.env.example`, `.gitignore`, Dockerfile and `.dockerignore`. It holds no `.env` file, no key, no private dataset folder, no run output and no cache. The Docker build context excludes secrets the same way through `.dockerignore`.

What will not reproduce from the shipped fixtures, by design: the MOT20 long video verdict. From fixtures alone, `python -m blindspot_ci.cli temporal-report --run e30e0efcc7ca43a7` fails because the run file is not shipped, and gating that id fails with exit code 4 for the same reason. Rebuilding needs the owner local MOT20 manifest and the saved raw stream as set out in `docs/long-video-test.md`. MOT20 is CC BY-NC-SA 3.0 non-commercial data, must not be redistributed and must never be committed. Treat the long video as documented evidence with rebuild steps, never as a locally reproducible judge step.

## Submission checklist, short form

The full merged list with artifact checks is `docs/SUBMISSION_CHECKLIST.md`. Items marked UNVERIFIED have not been checked against the official Rules. The event page is https://cerebralvalley.ai/e/meta-ai-developer-hackathon and lists a deadline of Nov 4 2026, 9:00 PM ET. Submit by 8:00 PM ET and re-open the link to confirm.

- [ ] Read the official Rules end to end. Required fields, eligibility, judging weights and any model use terms are UNVERIFIED until then.
- [ ] Choose the track, Indie or Startup, undecided today. Record the choice and why before submitting.
- [ ] Confirm the video length limit and the repository and write-up requirements against the Rules, not against secondary posts.
- [ ] Confirm what may be shown publicly: COCO photo licence before showing COCO photos, DAVIS research use limits, MOT20 non-commercial terms with no redistribution and no commit.
- [ ] Take the owner photos, label them with a named annotator, find a second annotator and run one fresh live experiment as listed under owner only blockers below. Until then the demo keeps the tray story as fixture practice.
- [ ] `python scripts/check.py` prints `Summary: PASS` on the final main commit, and GitHub CI is green on that same commit. CI runs ruff and pytest on Python 3.11 and 3.13 on every push and pull request. The docs style, attribution and secrets checks run in the local gate, so run both.
- [ ] Run `python scripts/package.py`, check the file list, and confirm no `.env` or API key in any package or image.
- [ ] No AI attribution in git history on the final range.
- [ ] Record the demo video from `docs/DEMO_SCRIPT.md`. Keep fixture steps labelled as fixture practice on screen or in narration. Play the finished video on another device or account, outside this machine, end to end.
- [ ] Evaluation card for each headline run downloaded and read once by a person.
- [ ] Write the final commit SHA and the CI run link into the submission notes. Rotate the API key afterwards if the project folder was ever synced online or shared with a key in it.

## Judging

The event page names two tracks. Indie is for individual builders and students and is judged on creativity, technical ambition, and whether the project works. Startup is for teams and founders and is judged on technical execution and whether the project holds up in production. A secondary report gives project scoring weights of impact 30 percent, creative use of Meta AI tools 25 percent, the demo including its video 25 percent, and technical depth and execution 20 percent. Those weights are UNVERIFIED against the official Rules. Source: https://madrobot.blog/2026/10/03/meta-global-ai-developer-hackathon-1-million-prizes-muse-model-api/

## Owner only blockers

- Take 28 or more photos of the red safety tag on the maintenance tray after the model release, across normal, low_light, small_object, truncated and absent. Until they exist the training overlap check keeps GO_CANDIDATE out of reach and the tray story stays fixture practice.
- Label every photo with the local label tool with a named annotator on each label, import them, and keep the private manifest out of git.
- Find a second annotator for at least 30 percent of cases, run `compare-labels`, and keep the agreement file for the gate. Target kappa at least 0.60.
- Run one fresh live experiment on the owner set inside the stated caps and gate it. Budget first with the free commands.
- Check the SAM 2 and SAM 3 papers before quoting any training overlap claim. DAVIS likely seen is UNVERIFIED today.
- Choose the track, read the official Rules, deploy the mock demo from `docs/free-deployment.md` and record the video. Keep any public deployment on the mock provider with no key and no live flag, because the app has no sign-in.

## Reference facts

- Pricing used for estimates: Muse Spark 1.3 Standard $1.25 per million input tokens and $4.25 per million output tokens. SAM 3.1 is $2.50 per 1,000 images. Default spend cap is $5 per run. The saved COCO example cost 0.33 US dollars and the saved DAVIS example cost 0.28 US dollars. Re-reading either saved run costs nothing.
- Saved example runs: COCO `a165cd6773cd433a` with decision NO_GO and DAVIS `8f6003378706480a` with decision NEEDS_REVIEW, both in `fixtures/examples`. The long video policy is `fixtures/policies/long-video.json`. Long video run files stay local only by licence.
- Keep to Meta terms: do not share keys, do not bypass rate limits, use Standard mode, keep Meta labels on real outputs, use only authorized media. The official Rules are authoritative.
