# BLINDSPOT CI

A test harness plus a conservative Release Gate that tells a QA engineer whether a vision model (Meta SAM 3.1)
is ready to ship, why, and what to fix first. Scores come from plain Python against human labels, never from a model.

On the saved live COCO run (`a165cd6773cd433a`) the gate says NO_GO: low light found 6 of 10 objects and
small objects 19 of 24, against a bar of 9 of 10 (the Release Gate, `docs/release-gate.md`).

| Decision | Exit code | Plain meaning |
| --- | --- | --- |
| GO_CANDIDATE | 0 | every check passed, a person still decides |
| NO_GO | 1 | a kind of photo that must work is below the bar |
| NEEDS_REVIEW | 2 | nothing clearly fails, but the evidence is thin, unchecked or not live |
| DEMO_ONLY | 3 | the answers came from a script or generated images |

Exit code 4 means a file could not be read. GO_CANDIDATE is not a safety approval.

- The app: run `python -m blindspot_ci.cli serve`, then open http://127.0.0.1:8000/app
- How it works page: http://127.0.0.1:8000/guide
- The decision rules: `docs/release-gate.md`

## What was tested

All three results are real SAM 3.1 answers scored against human labels. Details and run ids are in
`docs/real-results.md`.

- COCO val2017, live, 132 photos (run `a165cd6773cd433a`): NO_GO. Low light found 6 of 10, small objects 19 of 24.
- DAVIS 2017 video frames, live, 112 frames from 14 clips (run `8f6003378706480a`): NEEDS_REVIEW. SAM may have
  seen DAVIS in training. This is UNVERIFIED, from summaries of the SAM 2 and SAM 3 papers that should be read
  before it is quoted.
- Real long video test, live, one public MOT20-03 crowd video of 2,405 frames, 16 people followed from box prompts
  (corrected run `e30e0efcc7ca43a7`): NO_GO. Only 3 of 16 people were followed correctly on at least 90 percent
  of their scored frames, the median person on 82.5 percent. Most failures were a box returned with weak overlap,
  not a missing target. The first scoring (run `8c351fcde7154e21`) wrongly showed 0 of 16 because of a size
  mismatch bug: the service shrank the clip and returned boxes at that smaller size. We found it, fixed it and
  re-scored the saved raw text for free. One paid call, about 0.48 US dollars for the whole test.

The saved COCO and DAVIS runs used a scripted test order, not an agent choosing the tests. The Muse Spark agent
planner is implemented, but it did not produce these results.

## What was NOT tested

- The original planned use case, a red safety tag on a maintenance tray. No photos of it exist yet.
- Your own photos taken after the model release. Until they exist, GO_CANDIDATE cannot be reached.
- A second annotator. Most labels come from one person.
- More than one long video sequence. MOT20-02 and MOT20-05 were not run because their 76 and 86 MB uploads hung.
- Any GO_CANDIDATE decision. It has never been reached.

## Quick start

Requires Python 3.11 or newer. CI tests 3.11 and 3.13. The `pyproject.toml` says 3.10, but 3.10 is not tested.
The mock mode needs no GPU, key or network and costs nothing.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/check.py
python -m blindspot_ci.cli serve
```

The project gate uses a private temporary folder and prints `Summary: PASS`; if plain pytest reports a temporary folder permission error, run it with `--basetemp` pointing to a folder you own.

Open http://127.0.0.1:8000. The home page shows a saved real result, `/guide` explains how it works, and `/app`
is the full result page and tool. The offline provider is a deterministic mock and the page banner says so.
Mock results prove the code runs and say nothing about SAM.

## Reproduce each real result for free

The COCO and DAVIS run files are committed in `fixtures/examples`. Point the reader at that folder and every
command below makes no model call and spends nothing.

```powershell
$env:BLINDSPOT_RUNS_DIR = "fixtures/examples"
python -m blindspot_ci.cli release-gate --run a165cd6773cd433a    # NO_GO, exit 1
python -m blindspot_ci.cli release-gate --run 8f6003378706480a    # NEEDS_REVIEW, exit 2
python -m blindspot_ci.cli iou-sweep --run a165cd6773cd433a       # pass rate at IoU bars 0.25 to 0.75
python -m blindspot_ci.cli slice-tests --run a165cd6773cd433a     # exact tests with Holm correction
```

The long video run files stay local in `artifacts/runs` and are not committed, because MOT20 is non-commercial
data. See `docs/real-results.md` and `docs/long-video-test.md` for how to rebuild and re-read them.

## How a live run is paid and capped

Live runs need a Meta Model API key in `.env` as `MODEL_API_KEY`, `BLINDSPOT_PROVIDER=meta` and
`LIVE_API_ENABLED=true`. Nothing paid happens without both. A SAM call costs about a quarter of a cent. A call
limit (`BLINDSPOT_MAX_CALLS`) and a dollar cap (`BLINDSPOT_BUDGET_USD`, default 5.00) stop a run early. The long
video command reserves its budget before each call and does not retry. Using standard mode matters: contributor
mode lets Meta train on submitted content. Never put a key in source, screenshots or an archive. Image bytes leave
your computer on live runs, so use only images you are allowed to send.

## How it works

```
labeled cases -> test order (script or Muse Spark agent) -> SAM 3.1 segments -> parser
   -> Python scores IoU against the human box -> result returns to the planner -> next test or finish
```

- The planner never sees labels. They stay on the server until a case is scored.
- Statuses: `PASS`, `FAIL_FALSE_NEGATIVE`, `FAIL_FALSE_POSITIVE`, `FAIL_LOCALIZATION`, `UNKNOWN`, `ERROR`.
  The last two are not scored.
- The pass threshold is IoU 0.35 (`BLINDSPOT_MIN_IOU`).
- Each run records the image hash, IoU, latency, source label, cost and the planner's stated reason.
- Reports are written to `artifacts/runs/<id>.json`.
- The Release Gate reads one saved run and returns a decision, one line per check, the failing conditions and the
  next experiments. Mock, fixture, synthetic, generated and corrupted evidence can only give DEMO_ONLY. A training
  overlap check keeps GO_CANDIDATE out of reach for sets SAM may have seen. By-clip intervals show only with
  5 or more clips, otherwise n/a.

### Source labels

| Label | Meaning |
| --- | --- |
| `MOCK_FIXTURE` | scripted offline answer; proves the code runs, says nothing about SAM |
| `LIVE_META` | a real SAM 3.1 call made for this run |
| `CACHE_LIVE_META` | a real SAM 3.1 answer saved earlier and replayed |
| `CACHE_MOCK_FIXTURE` | a saved fixture answer |

## Models used

| Model | Job |
| --- | --- |
| Muse Spark 1.3 | the optional agent planner: picks tests by function calling (implemented, not what produced the saved results) |
| SAM 3.1 | the model under test: boxes and masks |
| Muse Image 1.0 | labeled low-light, glare and blur variants (`stress-gen`); the box is inherited and must be confirmed by a person |
| Muse Voice Transcribe 1.0 | turns a spoken reviewer note into text |
| Muse Wonder 1.0 | writes a plain-language audit of a finished run |

Only Python produces scores. Image, voice and audit output never changes one.

## Command line

```powershell
python -m blindspot_ci.cli experiment                  # run the experiment (mock unless live is enabled)
python -m blindspot_ci.cli import-photos FILE --dataset real|open|hard|video|coco
python -m blindspot_ci.cli label                       # draw boxes on your own photos
python -m blindspot_ci.cli card --run <id>             # evaluation card
python -m blindspot_ci.cli compare-agent --run <id>    # agent order against random order
python -m blindspot_ci.cli replay-planner --run <id> --steps K [--planner mock]    # offline policy comparison on saved outcomes
python -m blindspot_ci.cli compare-runs --baseline <id> --candidate <id>   # paired exact regression gate, exit 1 on a significant regression
python -m blindspot_ci.cli compare-labels a.json b.json                    # annotator agreement (kappa, IoU)
python -m blindspot_ci.cli coverage [--dataset NAME]    # case counts per condition, flags thin cells
python -m blindspot_ci.cli corrupt-gen                 # free, deterministic corruptions of real photos
python -m blindspot_ci.cli release-gate --run <id> [--policy P] [--agreement A]   # GO_CANDIDATE, NEEDS_REVIEW, NO_GO or DEMO_ONLY; see docs/release-gate.md
python -m blindspot_ci.cli iou-sweep --run <id> [--bars 0.25 0.5]   # pass rate across IoU bars, offline
python -m blindspot_ci.cli slice-tests --run <id>      # exact Fisher tests per condition with Holm correction, offline
python -m blindspot_ci.cli long-video --manifest M --sequences MOT20-03 --dry-run   # offline plan; live needs the owner's key
python -m blindspot_ci.cli temporal-report --run <id>  # read a saved long video report, offline
python -m blindspot_ci.cli diagnose                    # API check that prints no secrets
```

`python -m blindspot_ci.cli --help` lists the rest.

## Running against the live Meta API

Needs a Meta Model API key with models enabled, in standard mode. Cost and caps are described above.

```powershell
python -m pip install -e ".[live]"     # adds Meta's official meta-sam-parser
.\scripts\live_check.ps1               # one Muse Spark call and one SAM 3.1 call
.\scripts\live_experiment.ps1          # experiment with tool calling and SAM 3.1
```

Live runs need `BLINDSPOT_PROVIDER=meta` and `LIVE_API_ENABLED=true`. The scripts set them for their own
session only. A SAM call costs about a quarter of a cent, and a call limit and a dollar cap stop a run early.

The key goes in `.env` as `MODEL_API_KEY`. `.env` is ignored by git. Never put a key in source, screenshots
or an archive. Image bytes leave your computer on live runs, so use only images you are allowed to send.

If a call fails, run `python -m blindspot_ci.cli diagnose`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `BLINDSPOT_PROVIDER` | `mock` | `mock` or `meta` |
| `BLINDSPOT_PLANNER` | `heuristic` | `heuristic` or `muse` |
| `LIVE_API_ENABLED` | `false` | must be `true` before any paid call |
| `BLINDSPOT_DATASET` | `synthetic` | `synthetic`, `real`, `open`, `hard`, `video`, `coco`, `generated` or `corrupted` |
| `BLINDSPOT_MIN_IOU` | `0.35` | pass threshold for box overlap |
| `BLINDSPOT_MAX_ITERATIONS`, `BLINDSPOT_MAX_CALLS` | `4`, `16` | loop limits |
| `BLINDSPOT_BUDGET_USD` | `5.00` | spend cap per run |
| `BLINDSPOT_RUNS_DIR` | `artifacts/runs` | where reports are saved |
| `BLINDSPOT_HOST`, `BLINDSPOT_PORT` | `127.0.0.1`, `8000` | server address; non-loopback is refused when live is enabled |
| `MODEL_API_KEY` | empty | Meta key, local only |
| `META_BASE_URL` | `https://api.meta.ai/v1` | API base URL |
| `META_TEXT_MODEL`, `META_SAM_MODEL` | `muse-spark-1.3`, `sam-3.1` | model ids |
| `META_IMAGE_MODEL`, `META_VOICE_MODEL`, `META_WONDER_MODEL` | `muse-image-1.0`, `muse-voice-transcribe-1.0`, `muse-wonder-1.0` | model ids |

## HTTP API

```text
GET  /health                    liveness and provider name
GET  /api/info                  mode, dataset, planner and limits
GET  /api/cases                 test inventory without labels
GET  /api/cases/{id}/image      the photo for one case
POST /api/experiment            {"max_steps": 5}; 403 unless live is enabled
GET  /api/runs/{id}             a saved report with notes and audit
GET  /api/runs/{id}/release-gate release-gate decision and checks for a saved run
POST /api/runs/{id}/notes       typed reviewer note
POST /api/runs/{id}/voice       raw WAV body, transcribed into a note
POST /api/runs/{id}/audit       Muse Wonder audit of a saved run
POST /api/stress                Muse Image variants; 403 unless live is enabled
```

The server accepts only loopback Host headers and same-origin POSTs. It has no sign-in, so keep any public
deployment on the mock provider.

## Docker

```powershell
docker build -t blindspot-ci .
docker run --rm -p 8000:8000 blindspot-ci
```

The image runs as a non-root user on the mock provider. Pass a key only for a local, private run.

## Documentation

- `docs/dataset.md`: photograph, label and import your own evidence set
- `docs/results-open-images.md`: live result on everyday red coloured objects from Open Images
- `docs/results-hard-and-video.md`: harder photos and DAVIS video frames, with limits
- `docs/results-coco.md`: 132 COCO val2017 cases with a low-light weak spot
- `docs/real-results.md`: the three real results with run ids, caveats and free commands
- `docs/long-video-test.md`: the MOT20 long video pipeline and its limits
- `docs/release-gate.md`: the release gate decisions, checks, policy and exit codes
- `docs/gap-analysis.md`: what is missing against what standards and strong teams ask for
- `docs/deploy-and-readiness.md`: run and deploy notes, review findings, open items
- `docs/research-and-standards.md`: sources behind the design
- `docs/design.md`: design rules and known limits
- `docs/demo-and-submission.md`: demo script and submission checklist

## Limits and honesty

- This is a test harness with a conservative gate. It is not a benchmark and not a safety approval. A person
  decides every release.
- Most labels come from one person, and the photo sets are small. A pass rate here is not a failure rate you can quote.
- Mock and fixture results are not model performance.
- Intervals treat frames as independent. Frames from one clip or track are correlated, so they overstate certainty.
- On COCO, low light at 6 of 10 against 113 of 122 for the rest has an exact p value of 0.0087 raw and 0.0612
  after Holm correction, so that label is not distinguishable from chance.
- MOT20 human boxes include hidden body parts, the camera is not fixed, and only one sequence with 16 people was run.
- Contest rules and deliverable requirements are UNVERIFIED until the owner reads the official Rules.

## Licences and data

- Code: MIT. See `LICENSE`. Meta's `meta-sam-parser` is installed separately and has its own license.
- MOT20 is CC BY-NC-SA 3.0, non-commercial data. It is not stored in this repository and must not be redistributed.
- DAVIS is for research use. Its frames are rebuilt by a script and kept out of git.
- COCO photo licensing is not yet confirmed for public display. Photos are kept out of git.

## Layout

```text
blindspot_ci/    package: providers, experiment loop, scoring, API, web UI
scripts/         dataset fetchers, live helpers, packaging, check
tests/           pytest suite
datasets/        manifests and photos (private sets are git-ignored)
fixtures/        scripted mock answers, policies and saved example runs
docs/            results, design and review notes
```
