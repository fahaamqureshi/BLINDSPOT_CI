# BLINDSPOT CI

BLINDSPOT CI is a release gate for vision models. It tests a model under test, here Meta SAM 3.1, against cases a person labeled, scores every answer with plain Python, and tells a QA engineer whether the model is ready to ship, why, and what to fix first. No model grades anything. It is an evaluation harness, not a benchmark and not a safety approval. A person decides every release.

Start here:

- App: run `python -m blindspot_ci.cli serve`, then open http://127.0.0.1:8000/app
- How it works: http://127.0.0.1:8000/guide
- Results live in one place: `docs/real-results.md`, with full tables in `docs/results-detail.md`
- Deploy the public mock demo: `docs/free-deployment.md`, with owner account steps
- Gate rules: `docs/release-gate.md`

## The decision

| Decision | Exit code | Plain meaning |
| --- | --- | --- |
| GO_CANDIDATE | 0 | every check passed, a person still decides |
| NO_GO | 1 | a kind of photo that must work is below the bar |
| NEEDS_REVIEW | 2 | nothing clearly fails, but the evidence is thin, unchecked or not live |
| DEMO_ONLY | 3 | the answers came from a script or generated images |

Exit code 4 means a file could not be read. GO_CANDIDATE is not a safety approval and has never been reached.

Saved example: on the live COCO run `a165cd6773cd433a` the gate says NO_GO. Low light found 6 of 10 objects and small objects 19 of 24, against a bar of 9 of 10.

## Quick start

Requires Python 3.11 or newer. The mock mode needs no GPU, key or network and costs nothing. Mock results prove the code runs and say nothing about SAM.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/check.py
python -m blindspot_ci.cli serve
```

Open http://127.0.0.1:8000. The home page shows a saved real result, `/guide` explains how it works, and `/app` is the full result page and tool. The project gate prints `Summary: PASS` when the tree is clean. If plain pytest reports a temporary folder permission error, run it with `--basetemp` pointing to a folder you own. CI runs ruff and pytest on Python 3.11 and 3.13.

## Results

All results below are real SAM 3.1 answers scored against human labels. Run ids, caveats and free re-read commands live in `docs/real-results.md`. Per-condition tables live in `docs/results-detail.md`.

- COCO val2017, live, 132 photos, run `a165cd6773cd433a`: NO_GO. Low light 6 of 10, small objects 19 of 24.
- DAVIS 2017 video frames, live, 112 frames from 14 clips, run `8f6003378706480a`: NEEDS_REVIEW. SAM may have seen DAVIS in training. This is UNVERIFIED and should be checked against the SAM papers before it is quoted.
- Long video, live, one public MOT20-03 crowd video of 2,405 frames, 16 people followed from box prompts, corrected run `e30e0efcc7ca43a7`: NO_GO. Only 3 of 16 people were followed correctly on at least 90 percent of their scored frames. The first scoring wrongly showed 0 of 16 because the service returned boxes at a smaller size. The bug was fixed and the saved raw text was re-scored for free. One paid call, about 0.48 US dollars.

The saved COCO and DAVIS runs used a scripted test order, not an agent choosing the tests. The Muse Spark agent planner is implemented, but it did not produce these results.

Not tested yet:

- The original planned use case, a red safety tag on a maintenance tray. No photos of it exist yet.
- Photos taken after the model release. Until they exist, GO_CANDIDATE cannot be reached.
- A second annotator. Most labels come from one person.
- More than one long video sequence, and any GO_CANDIDATE decision.

## Reproduce each real result for free

The COCO and DAVIS run files are committed in `fixtures/examples`. These commands make no model call and spend nothing.

```powershell
$env:BLINDSPOT_RUNS_DIR = "fixtures/examples"
python -m blindspot_ci.cli release-gate --run a165cd6773cd433a
python -m blindspot_ci.cli release-gate --run 8f6003378706480a
python -m blindspot_ci.cli iou-sweep --run a165cd6773cd433a
python -m blindspot_ci.cli slice-tests --run a165cd6773cd433a
```

The long video run files stay local in `artifacts/runs` and are not committed, because MOT20 is non-commercial data. See `docs/real-results.md` and `docs/long-video-test.md` for how to rebuild and re-read them.

## Deploy

Local use is the main mode. For a public demo, follow `docs/free-deployment.md`: it deploys the scripted mock demo only, with no key and no private photos, and lists the owner account steps. Keep any public deployment on the mock provider, because the app has no sign-in.

```powershell
docker build -t blindspot-ci .
docker run --rm -p 8000:8000 blindspot-ci
```

The image runs as a non-root user on the mock provider. Pass a key only for a local, private run. What was reviewed and what is still open before production use is recorded in `docs/deploy-and-readiness.md`.

## How it works

```text
labeled cases, then test order (script or Muse Spark agent), then SAM 3.1 segments, then parser,
then Python scores IoU against the human box, then the result returns to the planner, then next test or finish
```

- The planner never sees labels. They stay on the server until a case is scored.
- Statuses are `PASS`, `FAIL_FALSE_NEGATIVE`, `FAIL_FALSE_POSITIVE`, `FAIL_LOCALIZATION`, `UNKNOWN` and `ERROR`. The last two are not scored.
- The pass threshold is IoU 0.35, set by `BLINDSPOT_MIN_IOU`. Each run records the image hash, IoU, latency, source label, cost and the planner reason. Reports are written to `artifacts/runs/<id>.json`.
- The Release Gate reads one saved run and returns a decision, one line per check, the failing conditions and the next experiments. Mock, fixture, synthetic, generated and corrupted evidence can only give DEMO_ONLY.

| Source label | Meaning |
| --- | --- |
| `MOCK_FIXTURE` | scripted offline answer, proves the code runs, says nothing about SAM |
| `LIVE_META` | a real SAM 3.1 call made for this run |
| `CACHE_LIVE_META` | a real SAM 3.1 answer saved earlier and replayed |
| `CACHE_MOCK_FIXTURE` | a saved fixture answer |

| Model | Job |
| --- | --- |
| Muse Spark 1.3 | optional agent planner, picks tests by function calling |
| SAM 3.1 | model under test, boxes and masks |
| Muse Image 1.0 | labeled stress variants, the box is inherited and must be confirmed by a person |
| Muse Voice Transcribe 1.0 | turns a spoken reviewer note into text |
| Muse Wonder 1.0 | writes a plain-language audit of a finished run |

Only Python produces scores. Image, voice and audit output never changes one.

## Command line

```powershell
python -m blindspot_ci.cli experiment
python -m blindspot_ci.cli import-photos FILE --dataset real|open|hard|video|coco
python -m blindspot_ci.cli label
python -m blindspot_ci.cli card --run <id>
python -m blindspot_ci.cli compare-runs --baseline <id> --candidate <id>
python -m blindspot_ci.cli coverage
python -m blindspot_ci.cli release-gate --run <id>
python -m blindspot_ci.cli long-video --manifest M --sequences MOT20-03 --dry-run
python -m blindspot_ci.cli diagnose
```

`python -m blindspot_ci.cli --help` lists the rest, including `compare-agent`, `replay-planner`, `compare-labels`, `corrupt-gen`, `iou-sweep`, `slice-tests` and `temporal-report`.

Live runs need a Meta Model API key in `.env` as `MODEL_API_KEY`, plus `BLINDSPOT_PROVIDER=meta` and `LIVE_API_ENABLED=true`. Nothing paid happens without both. A call limit, `BLINDSPOT_MAX_CALLS`, and a dollar cap, `BLINDSPOT_BUDGET_USD` with default 5.00, stop a run early. Never put a key in source, screenshots or an archive. Image bytes leave your computer on live runs, so use only images you are allowed to send. Helper scripts are `scripts/live_check.ps1` and `scripts/live_experiment.ps1`. If a call fails, run `python -m blindspot_ci.cli diagnose`.

Key settings, with defaults: `BLINDSPOT_PROVIDER` is `mock`, `BLINDSPOT_PLANNER` is `heuristic`, `LIVE_API_ENABLED` is `false`, `BLINDSPOT_DATASET` is `synthetic`, `BLINDSPOT_RUNS_DIR` is `artifacts/runs`, and `BLINDSPOT_HOST` with `BLINDSPOT_PORT` are `127.0.0.1` and `8000`. Non-loopback binding is refused while live mode is enabled. See `.env.example` for the local template.

## HTTP API

```text
GET  /health
GET  /api/info
GET  /api/cases
GET  /api/cases/{id}/image
POST /api/experiment
GET  /api/runs/{id}
GET  /api/runs/{id}/release-gate
POST /api/runs/{id}/notes
POST /api/runs/{id}/voice
POST /api/runs/{id}/audit
POST /api/stress
```

The server accepts only loopback Host headers and same-origin POSTs. It has no sign-in, so keep any public deployment on the mock provider.

## Documentation

Results and evidence:

- `docs/real-results.md`: the one home for results, three real results with run ids, caveats and free commands
- `docs/results-detail.md`: detail appendix with per-condition tables for COCO, Open Images and DAVIS
- `docs/dataset.md`: photograph, label and import your own evidence set
- `docs/long-video-test.md`: the MOT20 long video pipeline and its limits

How it works and how to judge it:

- `docs/release-gate.md`: gate decisions, checks, policy and exit codes
- `docs/design.md`: design rules and known limits
- `docs/gap-analysis.md`: what is missing against what standards and strong teams ask for
- `docs/research-and-standards.md`: sources behind the design

Ship and present:

- `docs/free-deployment.md`: free public deployment of the mock demo, with owner account steps
- `docs/deploy-and-readiness.md`: production readiness record, review findings and open items
- `docs/demo-and-submission.md`: demo script and submission checklist

Working method:

- `docs/agent-workflow.md`: reusable task prompt, loop rules and verification checklist
- `docs/skills-evaluation.md`: agent skill verdicts behind the workflow notes
- `docs/craft-anything-check.md`: three-width visual check method and findings

## Limits and honesty

- Most labels come from one person, and the photo sets are small. A pass rate here is not a failure rate you can quote. Quote counts with their interval, never a bare percentage.
- Mock and fixture results are not model performance.
- Intervals treat frames as independent. Frames from one clip or track are correlated, so they overstate certainty.
- On COCO, low light at 6 of 10 against 113 of 122 for the rest has an exact p value of 0.0087 raw and 0.0612 after Holm correction, so that slice is not distinguishable from chance on its own.
- MOT20 human boxes include hidden body parts, the camera is not fixed, and only one sequence with 16 people was run.
- Contest rules and deliverable requirements are UNVERIFIED until the owner reads the official Rules.

## Licences and data

- Code: MIT. See `LICENSE`. The `meta-sam-parser` package is installed separately and has its own license.
- MOT20 is CC BY-NC-SA 3.0 non-commercial data. It is not stored in this repository and must not be redistributed.
- DAVIS is for research use. Its frames are rebuilt by a script and kept out of git.
- COCO photo licensing is not yet confirmed for public display. Photos are kept out of git.

## Layout

```text
blindspot_ci/    package: providers, experiment loop, scoring, API, web UI
scripts/         dataset fetchers, live helpers, packaging, check
tests/           pytest suite
datasets/        manifests and photos, private sets are git-ignored
fixtures/        scripted mock answers, policies and saved example runs
docs/            results, design and review notes
```
