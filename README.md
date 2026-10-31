# BLINDSPOT CI

An evaluation tool that finds where a vision model misses objects it should see.

You give it photos in which a person has marked where an object is (or confirmed it is absent). An agent
(Muse Spark) chooses which photo to test next. The model under test (SAM 3.1) outlines the object. Plain
Python then scores the outline against the person's box. No model grades itself.

It is a test harness, not a benchmark and not a safety approval.

## What you get

- A pass count per condition (low light, small object, truncated, lookalike, absent) with Wilson 95 percent intervals.
- Every failure shown on its photo, with the human box beside the model's.
- An evaluation card in Markdown: intended use, evidence, metrics, failures, reproducibility, limits.
- Runs that replay from a cache and carry a source label, so mock results are never mistaken for model results.

## Results so far

Real, human-labeled photos and video only. Details and caveats are in `docs/`.

| Set | Source | Cases | Passed | Notes |
| --- | --- | --- | --- | --- |
| Open Images | fire hydrants, stop signs | 22 scored | 20 | two labels adjudicated by the owner, originals kept |
| Harder Open Images | low light, small, truncated | 21 | 20 | one dark traffic light missed |
| DAVIS 2017 video | 112 frames, 14 clips | 112 | 111 | mean mask J 0.926 against human masks |
| COCO val2017 | hydrants, stop signs, traffic lights | 132 | 119 | weakest slice is low light, 6 of 10 |

These samples are small and mostly single-annotator. A pass rate here is not a failure rate you can quote.
See `docs/gap-analysis.md` for what is missing.

## Quick start

Requires Python 3.11 or newer. No GPU, key or network is needed for the offline mode.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m pytest
python -m blindspot_ci.cli serve
```

Open http://127.0.0.1:8000. The overview has an interactive IoU playground, `/demo` is a free guided run,
`/guide` covers setup, and `/app` is the full tool. The offline provider is a deterministic mock and the page
banner says so.

## How it works

```
labeled cases -> agent picks a test (function call) -> SAM 3.1 segments -> parser
   -> Python scores IoU against the human box -> result returns to the agent -> next test or finish
```

- The agent never sees labels. They stay on the server until a case is scored.
- Statuses: `PASS`, `FAIL_FALSE_NEGATIVE`, `FAIL_FALSE_POSITIVE`, `FAIL_LOCALIZATION`, `UNKNOWN`, `ERROR`.
  The last two are not scored.
- The pass threshold is IoU 0.35 (`BLINDSPOT_MIN_IOU`).
- Each run records the image hash, IoU, latency, source label, cost and the agent's stated reason.
- Reports are written to `artifacts/runs/<id>.json`.

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
| Muse Spark 1.3 | the agent: picks each test by function calling |
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
python -m blindspot_ci.cli compare-runs --baseline <id> --candidate <id>   # regression gate, exit 1 on a drop
python -m blindspot_ci.cli compare-labels a.json b.json                    # annotator agreement (kappa, IoU)
python -m blindspot_ci.cli corrupt-gen                 # free, deterministic corruptions of real photos
python -m blindspot_ci.cli diagnose                    # API check that prints no secrets
```

`python -m blindspot_ci.cli --help` lists the rest.

## Running against the live Meta API

Needs a Meta Model API key with models enabled, in standard mode (contributor mode lets Meta train on
submitted content, so do not use it).

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
- `docs/results-open-images.md`: live result on real Open Images photos
- `docs/results-hard-and-video.md`: harder photos and DAVIS video frames, with limits
- `docs/results-coco.md`: 132 COCO val2017 cases with a low-light weak spot
- `docs/gap-analysis.md`: what is missing against what standards and strong teams ask for
- `docs/deploy-and-readiness.md`: run and deploy notes, review findings, open items
- `docs/research-and-standards.md`: sources behind the design
- `docs/design.md`: design rules and known limits
- `docs/demo-and-submission.md`: demo script and submission checklist

## Layout

```text
blindspot_ci/    package: providers, experiment loop, scoring, web UI
scripts/         dataset fetchers, live helpers, packaging
tests/           pytest suite
datasets/        manifests and photos (private sets are git-ignored)
fixtures/        scripted mock answers
docs/            results, design and review notes
```

## License

MIT. See `LICENSE`. Meta's `meta-sam-parser` is installed separately and has its own license.
