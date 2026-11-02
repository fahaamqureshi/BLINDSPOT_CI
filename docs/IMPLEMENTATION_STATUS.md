# Implementation status

Audit date: 2026-11-03. Base commit: origin main at 632f283 after rebase (parent ea84e00 plus later docs commits). Method: every claim below points to a file and line that was read in this checkout, or to a command that was run and whose output is recorded in `docs/TEST_RESULTS.md`. No live API call was made. No secret value was read or printed.

This file maps the repository against the master directive workflow, Phases A to I, and the ten P0 items. Status words mean: DONE (built and covered by tests or a saved run), PARTIAL (built but with a stated gap), MISSING (not built), MOCK-ONLY (works only with scripted answers). The directive text itself is not stored in this repository, so the phase names below follow the pipeline described in README lines 84 to 92 and the module layout in `blindspot_ci/`.

## Phase map

| Phase | What it covers | Status | Evidence |
| --- | --- | --- | --- |
| A. Labeled cases and datasets | Person labels, manifests, validation, label hiding | DONE for code, PARTIAL for data | `blindspot_ci/experiment/cases.py` lines 15 to 23 (manifests and visibilities), lines 80 to 112 (box validation), line 141 onward (`public_case` hides labels). Only `datasets/manifest.json` with 5 synthetic cases is committed. Real, open, hard, video and coco manifests are git-ignored and absent in this checkout, confirmed by the coverage run in `docs/TEST_RESULTS.md`. |
| B. Planner and agent loop | Bounded choice of the next test, labels hidden | DONE (two planners), PARTIAL for evidence | `blindspot_ci/experiment/planners.py` line 36 (`MockToolPlanner`), line 109 (`MuseToolPlanner`), PROSE: tools defined near line 76. Saved COCO and DAVIS runs record planner MOCK_POLICY, so the Muse planner did not produce the headline results. README line 48 says the same. |
| C. Model under test | SAM 3.1 boxes and masks, plus long video tracking | DONE (live history), MOCK-ONLY today | `blindspot_ci/providers/meta.py` line 164 (`MetaSam31Adapter`), `blindspot_ci/providers/sam_video.py` line 237 (video adapter). Saved runs `fixtures/examples/a165cd6773cd433a.json` and `8f6003378706480a.json` record mode LIVE_META. This audit ran mock mode only. |
| D. Parsing | Turn SAM text into boxes and masks | DONE | `blindspot_ci/providers/sam_output.py` (`parse_sam_output`, parser status values), `blindspot_ci/providers/sam_video.py` (frame parser). Only a structured parse is scored; the runner raises otherwise in `blindspot_ci/experiment/runner.py`. |
| E. Scoring | Plain Python IoU scoring, six statuses | DONE | `blindspot_ci/experiment/scoring.py` line 17 (default IoU 0.35), line 89 (`score_case`), line 24 (Wilson interval), line 21 (minimum slice size 5). Statuses are PASS, FAIL_FALSE_NEGATIVE, FAIL_FALSE_POSITIVE, FAIL_LOCALIZATION, UNKNOWN and ERROR. UNKNOWN and ERROR are never scored. |
| F. Release gate | Four decisions with exit codes | DONE | `blindspot_ci/experiment/release_gate.py` line 21 (decision names), line 23 (exit codes), line 25 (live modes), lines 34 to 52 (default policy, 0.90 pass bar, 29 cases per condition, kappa 0.60). GO_CANDIDATE has never been reached: README line 22. |
| G. Persistence, cache, budget, provenance | Saved runs, replay, spend caps | DONE | `blindspot_ci/budget.py` line 12 (guard, reserve before spend), `blindspot_ci/cache.py` line 11 (JSON cache keyed by hash), `blindspot_ci/provenance.py` (append-only log), `blindspot_ci/experiment/runner.py` line 40 (run id pattern) and the run save step. |
| H. API and web UI | HTTP routes and the three pages | DONE (UX owned elsewhere) | `blindspot_ci/api.py` lines 67 to 99 (pages and health), lines 161 to 390 (JSON routes). Pages live in `blindspot_ci/web/` and are owned by the UX worker in this programme; this audit did not edit them. Boot probe results are in `docs/TEST_RESULTS.md`. |
| I. Deployment and submission | Public mock demo, Docker, checklist | PARTIAL | `Dockerfile` (mock only, non-root user), `docs/free-deployment.md` (Northflank primary, Koyeb fallback). No hosted service was created by this audit. Owner steps remain in `docs/SUBMISSION_CHECKLIST.md`. |

## P0 scorecard (10 items)

| Item | Status | Evidence |
| --- | --- | --- |
| P0-1. Person-labeled cases with labels hidden from the planner | DONE (code), PARTIAL (own photos missing) | `cases.py` `public_case` returns id, title, condition, concept and image size only. `runner.py` scores after the provider call. The red safety tag owner set does not exist: README lines 50 to 55, `datasets/real-labels-template.json` is a template with placeholder values. |
| P0-2. Bounded planner that never sees labels and stops safely | DONE | `planners.py` Muse planner validates exactly one tool call, a known function and an untested case id, and stops otherwise. `agent.py` bounds the probe loop by iterations, calls and budget. `factory.py` line 63 builds the experiment runner. |
| P0-3. Live SAM 3.1 integration with honest source labels | DONE (history), not re-run here | `meta.py` SAM adapter, cost 2.50 USD per 1000 images. `runner.py` `source_label` gives MOCK_FIXTURE, LIVE_META or a CACHE form. Committed example runs are LIVE_META on every step. Live access was intermittent in past notes and was not retried, per the no-live-call rule. |
| P0-4. Deterministic Python scoring as the only judge | DONE | `scoring.py` is the only scorer for cases. `evaluator.py` does per-label counts for probe mode. Muse Image, Voice and Wonder never score: `providers/meta_extras.py` header, `api.py` audit route comment. |
| P0-5. Release gate with DEMO_ONLY guard and exit codes | DONE | `release_gate.py` demo reason check, live mode check, training overlap check. Mock, fixture, synthetic, generated and corrupted evidence can only give DEMO_ONLY. CLI exit codes 0 to 4 are documented in `docs/release-gate.md` and README lines 15 to 22. |
| P0-6. Spend caps, call limits and cache by input hash | DONE | `config.py` lines 34 to 36 (max iterations 4, max calls 16 default in code, budget 5.00 USD). `budget.py` reserves before each paid call and is thread-safe. `cache.py` hashes the key with SHA-256. `api.py` lines 117 to 126 keep one server-wide guard so repeated clicks cannot each spend a full budget. Live runs also need both the meta provider flag and the live flag in `factory.py` `_live_cfg`. |
| P0-7. Saved runs reproducible for free, with provenance | DONE for COCO and DAVIS, PARTIAL for long video | `fixtures/examples/` holds both run files (775093 and 2149479 bytes). Free re-read commands are in README lines 57 to 67 and were run for the gate in this audit. The long video run files stay local and are not committed because MOT20 is non-commercial: README line 69. Rebuild steps are in `docs/long-video-test.md`. |
| P0-8. API and web UI showing verdict, failures and fix list | DONE | Routes in `api.py`: `/health`, `/api/info`, `/api/cases`, `/api/experiment`, `/api/runs/{id}`, `/api/runs/{id}/release-gate`, `/api/examples`, `/api/stress`, `/api/corrupt`, notes, voice and audit. All probed routes returned 200 in mock mode; see `docs/TEST_RESULTS.md`. |
| P0-9. Security for local use: host guard, same-origin posts, upload checks | DONE for local use, MISSING sign-in and rate limit | `security.py` line 24 installs the local guard (loopback hosts, same-origin state-changing requests). `cli.py` serve step refuses a non-loopback bind while live mode is on. `media.py` line 6 caps images at 4000000 bytes. Voice WAV is capped at 32 MB and checked before budget is reserved in `api.py`. No sign-in exists, so a public deployment must stay on the mock provider: README line 73. |
| P0-10. Real evidence and honesty about limits | PARTIAL | Three real results exist (COCO NO_GO, DAVIS NEEDS_REVIEW, MOT20 long video NO_GO) in `docs/real-results.md`. GO_CANDIDATE has never been reached. Single labeler for most sets, small samples, and training overlap UNVERIFIED remain open. See the gap list below. |

Score: 7 DONE, 3 PARTIAL, 0 MISSING at code level. The three PARTIAL items are all evidence items, not code items: own photos, second labeler and broader real runs.

## Real versus simulated integrations

| Integration | Real or simulated | Evidence and honest note |
| --- | --- | --- |
| SAM 3.1 image segmentation | Real, with saved live runs | `providers/meta.py` SAM adapter posts to the Responses API with streaming. The request shape note in the class docstring says it was not confirmed against a live account in that comment, yet the committed COCO and DAVIS run files record LIVE_META with per-step latency, so live calls did succeed on 2026-10-31. Treat the docstring as stale caution, not as proof of failure. |
| SAM 3.1 long video | Real, one paid call | `providers/sam_video.py` video adapter, no retries, budget reserved before the call. One MOT20-03 call, plan price 0.481 USD. Later frames truncated at 2351 of 2405 count as errors. Details in `docs/real-results.md`. |
| Muse Spark planner (case mode) | Implemented, saved headline runs scripted | `experiment/planners.py` Muse planner uses Chat Completions function calling. It ran live on Open Images and DAVIS subsets per `docs/results-detail.md`, but the two committed example runs used MOCK_POLICY. No evidence it beats random order: `experiment/baseline.py` exact comparison, and the Open Images note in `docs/results-detail.md`. |
| Muse Spark planner (probe mode) | Implemented | `planner.py` Muse planner orders probes once per scenario with heuristic fallback. `providers/meta.py` Muse adapter returns probe lists only. |
| Mock vision provider | Simulated by design | `providers/mock.py` reads `fixtures/mock_responses.json`, model name mock-sam-3.1-shaped, cost always zero. It never reads ground truth. Results prove the code runs and say nothing about SAM. |
| Muse Image stress variants | Implemented, evidence is GENERATED only | `experiment/stress.py`: at most 6 variants per call, box inherited and marked not re-verified. Variants can only give DEMO_ONLY at the gate. Only run on synthetic drawings so far per `docs/results-detail.md`. |
| Measured corruptions | Real transforms, free, labels exact | `experiment/corruptions.py`: six corruptions, severities 1 to 5, at most 60 variants, pixels never moved so boxes stay exact. Dataset kind is MEASURED and still cannot pass the gate as live evidence. |
| Muse Voice Transcribe | Implemented | `providers/meta_extras.py` voice adapter, WAV only, 32 MB cap. Notes are saved with source MUSE_VOICE_TRANSCRIBE and never change a score. |
| Muse Wonder audit | Implemented | Same file, Wonder auditor with a fixed system prompt that forbids re-grading. Input is clipped and control characters are stripped in `audit_input`. Output is stored beside the run, clearly marked as model-written. |
| Meta key handling | Name checked, value never read | The variable name MODEL_API_KEY exists in `blindspot_ci/config.py` line 22, `.env.example` line 3 and `scripts/package.py` secret patterns. This worktree has no `.env` file (existence check only). No key value appears in this audit. Live mode needs the key plus both flags; errors redact the key in `providers/meta.py`. |

## Security and cost safeguards

Present:

- Spend cap per run and per server: `budget.py` reserve-before-call, `config.py` budget default 5.00 USD, `api.py` shared session guard.
- Call limits: experiment planner and agent loops are bounded by max steps (API allows 1 to 8), max calls and max iterations.
- Cache by input hash: `cache.py` SHA-256 file names; the experiment cache key includes provider, model, image SHA-256 and concept in `runner.py`, and the mock key also includes the fixture digest so edited fixtures cannot replay stale answers.
- Label hiding: `public_case` strips ground truth; the Muse prompt states labels stay hidden; case titles and notes are cleaned and marked untrusted in `planners.py`.
- Upload and media validation: image type and 4 MB cap in `media.py`, WAV header and size checks before charging in `api.py`, video upload MP4 and 1 GB cap with no retry in `sam_video.py`, image path confinement and box bounds in `cases.py`.
- Local-only guard: loopback Host allowlist plus same-origin check for state-changing requests in `security.py`; serve refuses a public bind with live mode on.
- Secret hygiene: `.env` is git-ignored, the Docker image excludes it, `scripts/package.py` scans an allowlist for secret-like strings, and `scripts/check.py` runs the same scan.

Missing or limited:

- No sign-in, no per-user rate limit. Safe only as a local tool or a public mock demo.
- No global cost ledger across server restarts; the session guard resets on restart.
- Run files, cache and provenance log grow without limit; clearing them is manual.
- The live cache key has no prompt version by design, so a changed SAM request format needs a manual cache clear. This is recorded in `docs/deploy-and-readiness.md`.

## Prioritized gap list

| Priority | Gap | Exact next implementation task |
| --- | --- | --- |
| P0 | No owner photos of the red safety tag on a maintenance tray, so the planned use case is untested and GO_CANDIDATE is unreachable | Owner takes 28 or more own photos after the model release across normal, low_light, small_object, truncated and absent, labels them with the label command, then runs one live experiment on the real dataset and gates it. Code side is ready; no code change needed first. |
| P0 | No second annotator agreement file for any headline run (gate checks FAIL for coverage and kappa) | A second person labels at least 30 percent of the same cases, then run the compare-labels command and pass the agreement file to the release-gate command. Record the kappa in the run notes. |
| P0 | Contest Rules, track choice and licence checks are UNVERIFIED | Owner reads the official Rules, picks Indie or Startup, confirms video length and write-up fields, and confirms the COCO photo licence before any public display. See `docs/SUBMISSION_CHECKLIST.md`. |
| P1 | Muse planner has no proven benefit over random order | Run compare-agent on a fully scored human-labeled set with enough failures (at least 10 failures), then publish the exact hypergeometric result either way. If it still shows no benefit, keep the scripted order for headline runs and say so. |
| P1 | Small samples: most conditions have 8 to 30 scored cases, below the 29 needed for the gate lower-bound check | Add cases per required condition until each reaches 29 scored with fresh photos, starting with low_light and small_object on the owner set. Re-run coverage after each import. |
| P1 | DAVIS training overlap is UNVERIFIED and COCO overlap is unknown | Owner checks the SAM 2 and SAM 3 papers, then updates the TRAINING_OVERLAP table in `release_gate.py` with a cited entry or keeps the fail. Do not quote the overlap claim before that check. |
| P1 | Long video evidence is one sequence, 16 people, with a truncated stream | Re-run MOT20-02 and MOT20-05 with the file upload fallback, or state the single-sequence limit in the submission. Fix the upload hang first if it recurs, with a bounded timeout test. |
| P2 | No reviewer sign-off step in the app | Add a sign-off endpoint that records reviewer name, decision and date beside a run, without changing scores, plus tests. Keep it local-only behind the existing guard. |
| P2 | No mask-quality metric for photo datasets (boxes only) | Extend the DAVIS mask scoring approach to any dataset that stores human polygons, and show mean J beside the box result on the card. Photo sets without polygons stay box-only and must say so. |
| P2 | Docker image written but not built in CI | Add one CI job that builds the image and curls the health route in mock mode, or record a manual build before submission. |

## What this audit did not do

- No live API call, no spend, no key read.
- No edits to source code, web files, README or other docs. Only the seven audit docs in the task were written.
- No claim that mock or fixture numbers describe SAM performance.
