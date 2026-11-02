# API contracts

This file is the contract a caller can rely on: HTTP routes in `blindspot_ci/api.py`, the CLI surface in `blindspot_ci/cli.py`, and the provider and planner interfaces. It describes what the code does today. Anything marked live needs a Meta key plus both enabling flags and will spend money; the audit made no live call.

## Shared rules

- Server default bind is 127.0.0.1 port 8000. The serve command refuses a non-loopback bind while live mode is on.
- Every request passes the local guard in `blindspot_ci/security.py`: the Host header must be loopback (or an allowed extra host), and a state-changing request with an Origin header must be same-origin. There is no sign-in.
- Settings come from the environment at each Settings construction in `blindspot_ci/config.py`. Defaults: provider mock, planner heuristic, live off, dataset synthetic, min IoU 0.35, max calls 16, budget 5.00 USD.
- Run ids must match 16 lowercase hex characters. A bad id is a 404 or a file error, never a guess.
- Error shape: FastAPI HTTPException with a detail string. Status use: 403 live calls off or missing key, 404 unknown run, case or dataset, 413 audio over 32 MB, 422 bad input or unusable provider output, 429 server spend cap used up, 502 provider failure.
- Scores are only produced by Python scoring. The notes, voice and audit routes store text beside a run and never change its numbers.

## HTTP routes

| Route | Input | Output | Spend |
| --- | --- | --- | --- |
| GET /health | none | status ok plus the configured provider name | free |
| GET / | none | home page HTML | free |
| GET /app | query run and dataset read by the page script | result page HTML | free |
| GET /guide | none | how it works page HTML | free |
| GET /demo | none | 307 redirect to / | free |
| GET /probes | none | 307 redirect to / | free |
| GET /site.css | none | shared stylesheet | free |
| GET /api/info | optional dataset query | mode label, provider, planner, live flag, min IoU, dataset id and kind, available datasets, model role list | free |
| GET /api/cases | optional dataset query | case list without labels (id, title, condition, concept, image URL, width, height, note) | free |
| GET /api/cases/{case_id}/image | dataset query | the photo file, or 404 with a licence note when the photo is not in the checkout | free |
| POST /api/experiment | JSON max_steps 1 to 8, optional dataset | the full run report (see run shape below) and saves it | spends only when provider is meta or planner is muse; counts against the server guard |
| GET /api/runs/{run_id} | run id | saved run merged with reviewer notes and audit extras; committed examples answer when the id is not saved locally | free |
| GET /api/runs/{run_id}/release-gate | run id | gate JSON: policy, traceability, checks, conditions, failing list, next experiments, notice | free |
| GET /api/runs/{run_id}/card | run id | evaluation card as Markdown download | free |
| GET /api/examples | none | one summary per committed example run, each summarised by the gate | free |
| POST /api/stress | JSON source, 1 to 3 edits, optional case ids | created variant ids, generated dataset name, estimated cost, inherited-box warning | live only, about 0.01 USD per image, at most 6 jobs; partial results are kept on failure |
| POST /api/corrupt | JSON source, 1 to 6 corruptions, severities, optional case ids | created variant ids, corrupted dataset name, zero cost, exact-label note | free to create; running the variants on SAM costs per case |
| POST /api/runs/{run_id}/notes | JSON case_id and text 1 to 1000 chars | the saved note with source typed | free |
| POST /api/runs/{run_id}/voice | raw WAV body, case_id query | the saved note with source MUSE_VOICE_TRANSCRIBE | live only; WAV checked before budget reserve; 32 MB cap |
| POST /api/runs/{run_id}/audit | run id | the saved audit (text, model, time, does-not-change-scores note) | live only; one Wonder call estimate reserved first |
| GET /api/scenarios | none | probe-mode scenario id list | free |
| GET /api/scenario | scenario_id query | one probe-mode scenario | free |
| POST /api/run | JSON scenario_id | probe-mode agent report | mock free; meta spends under the same guards |

Model role list returned by /api/info (fixed in code): Muse Spark 1.3 as agent, SAM 3.1 as segmenter, Muse Image for stress variants, Muse Voice Transcribe for spoken notes, Muse Wonder for the plain-language audit.

## Run report shape

A run report is one JSON object, saved as the run id plus .json, with reviewer extras in a sibling extras file. Fields a caller can rely on:

- id, started_at, finished_at: identity and UTC times.
- mode: one of MOCK_FIXTURE, LIVE_META, CACHE_LIVE_META, CACHE_MOCK_FIXTURE, or a MIXED form. The mode follows what the steps actually used, so a fully replayed live run never claims to be fresh live.
- provider, model, planner, planner_prompt_version: who answered and who picked the tests.
- dataset: id, type (kind), annotation_status.
- min_iou: the bar used for every case in the run.
- steps: one entry per tested case with the public case, the planner decision (case id, reason, planner, tool call id), the outcome (status, scoreable flag, IoU, reason), the ground truth revealed after scoring (visibility, box, label provenance), the prediction (source label, provider, model, latency, parser status, detections with box, confidence or null, mask summary), and the image SHA-256.
- summary: tested, scored, passed, failed, unknown, errors, pass rate, Wilson interval, underpowered flag, per-condition counts, failing case ids, and the not-a-safety-approval note.
- errors: plain strings for steps that could not run. An error step is saved with a null prediction and an ERROR outcome.
- calls and estimated_cost_usd: budget counters for the run. Estimates use list prices, not the provider bill.

Confidence is null when the API gives no score. The code never invents one.

## CLI surface

The entry point is `python -m blindspot_ci.cli`. Commands grouped by cost:

Free and offline: experiment in mock mode, release-gate, card, compare-runs, coverage, iou-sweep, slice-tests, temporal-report, compare-labels, compare-agent (scores from cache), replay-planner (refuses the live Muse planner so it makes zero network calls), label (local tool on port 8001), import-photos, adjudicate, corrupt-gen, long-video with dry-run or from-raw.

Live and paid, each guarded: experiment with the meta provider or muse planner, live-run, smoke-meta, smoke-sam, smoke-tools, smoke-models, stress-gen, transcribe, audit, diagnose (compares a fake key with the real key shape and prints no secret), long-video without dry-run.

Release gate exit codes: 0 GO_CANDIDATE, 1 NO_GO, 2 NEEDS_REVIEW, 3 DEMO_ONLY, 4 file could not be read. Experiment returns 1 when the report holds errors. Serve and label run long-lived local servers and are stopped by the operator.

## Provider and planner interfaces

Vision provider (`blindspot_ci/providers/base.py`): inspect takes a scenario and a probe and returns detections, raw text, usage, estimated cost, cache flag, parser status and notes. A provider must not read ground truth. Parser status structured is the only value that lets a result be scored; anything else forces review or an error step.

Case planner (`blindspot_ci/experiment/planners.py`): choose takes the public case map, the remaining ids and the measured history, and returns a decision (case id or null to stop, reason, planner name, tool call id). Record_result feeds the scored outcome back. The Muse implementation adds three hard rules: exactly one tool call per turn, a known function name, and a case id that is still untested. Breaking any rule stops the run safely.

Probe planner (`blindspot_ci/planner.py`): next_probe picks one remaining probe or stops. The heuristic planner is free and deterministic. The Muse planner orders probes once per scenario and falls back to the heuristic order on any failure.

Budget guard (`blindspot_ci/budget.py`): reserve raises before a call when the call limit or the dollar cap would be exceeded; charge adds spend made under a per-run guard to the shared server guard; exhausted reports a full cap. All operations hold one lock.

## Stability notes

- Additive fields may appear in run JSON; consumers should ignore unknown keys. The gate rejects unknown policy keys on purpose.
- The committed example run ids a165cd6773cd433a (COCO) and 8f6003378706480a (DAVIS) are stable fixtures. The long video run id is not stable across rebuilds: a replay always gets a new id.
- Dataset names are a fixed set: synthetic, real, open, hard, video, coco, generated, corrupted. An unknown name is an error with the valid set in the message.
