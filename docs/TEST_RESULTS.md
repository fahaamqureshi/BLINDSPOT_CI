# Test results

Closeout date: 2026-11-03. Verified code head: origin main at 65cdb9dc36082bce3a036bb5d257d5e7ebdf7948. Method: fresh clone from GitHub into a temp folder, editable install, then the commands below in mock mode only. No live API call was made in this closeout and no secret value was read or printed. Live run facts below are read from the committed records, not re-measured.

This file records exact commands and what they printed. A result without output is not claimed.

## Fresh clone and install

Commands, following the README quick start:

```powershell
git clone https://github.com/fahaamqureshi/BLINDSPOT_CI.git <temp folder>
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/check.py
```

Result: the clone landed on main at 65cdb9dc36082bce3a036bb5d257d5e7ebdf7948 with a clean tree. On this machine the literal py -3.11 step fails with No suitable Python runtime found, because only Python 3.13 is installed. The README requires Python 3.11 or newer, so the venv was created with py -3.13 instead and every step after that was unchanged. Python in the venv: 3.13.15. The editable install finished with Successfully installed blindspot-ci-0.1.0 and exit code 0. GitHub CI covers Python 3.11 and 3.13, so the 3.11 path is proven there.

## Project gate

Command:

```powershell
python scripts/check.py
```

Output (exact):

```text
PASS  ruff
PASS  pytest
PASS  docs style
PASS  attribution
PASS  secrets

Summary: PASS
```

Exit code 0. The gate runs ruff, pytest, a docs style scan over README and docs markdown, a git attribution scan, and a secret scan from scripts/package.py. The style scan bans em dashes, ellipsis characters, three dots, asterisks and emojis in docs prose (fenced code and inline code are excluded).

## Lint and tests on their own

Command:

```powershell
python -m ruff check blindspot_ci scripts tests
```

Output: All checks passed. Exit code 0.

Command (owned temp folder, cache disabled, because plain pytest on this Windows machine fails at setup with PermissionError on the shared pytest temp folder, which the README already warns about):

```powershell
python -m pytest --basetemp=<owned temp folder> -p no:cacheprovider
```

Output tail: 331 passed, 3 warnings in 6.23s. Exit code 0. Collect-only reports 331 tests collected.

Collected tests by file (from collect-only): test_agent 1, test_agent_loop 26, test_api 7, test_budget_cache 4, test_check 8, test_cli 7, test_cluster_ci 8, test_coverage 8, test_custom_scenario 7, test_evaluator 1, test_examples_api 4, test_experiment_api 6, test_experiment_cases 17, test_experiment_runner 21, test_experiment_scoring 14, test_importer 12, test_iou_sweep 4, test_labeler 3, test_live_adapter 23, test_meta_contract 19, test_meta_extras 28, test_mot_importer 5, test_package 4, test_planner 11, test_release_gate 26, test_release_gate_api 3, test_replay 4, test_sam_video 18, test_security_reliability 9, test_slice_tests 4, test_temporal 19. Total 331 in 31 files.

Focused run required by the closeout:

```powershell
python -m pytest --basetemp=<owned temp folder> -p no:cacheprovider tests/test_agent_loop.py
```

Output tail: 26 passed in 0.75s. Exit code 0. That file checks the nine bounded agent tools with closed schemas, argument validation, observation driven replanning, label hiding, budget and cancellation stops, repeat justification, and that the planner cannot touch scores, thresholds or the release gate.

Coverage note: the suite covers scoring, the gate, planners, the agent loop, the API, the video parser, corruptions through the API tests, budget and cache, packaging and the checker itself. It runs fully offline in mock mode, so a green suite proves the code path, not live model behaviour.

## Submission package

Command:

```powershell
python scripts/package.py
```

Output: Wrote dist/blindspot-ci-0.1.0.zip with 143 files. Exit code 0.

The ZIP was listed and checked. It holds 143 entries: README, LICENSE, pyproject.toml, .env.example, .gitignore, Dockerfile and .dockerignore, the blindspot_ci package with its web pages, 31 test files plus conftest, all docs markdown, fixtures with both saved example runs, the long video policy, expected demo, ground truth and mock responses, data/scenarios.json, datasets/manifest.json, datasets/real-labels-template.json, the 5 synthetic sample drawings, the scripts folder, and the CI workflow. Checks that passed: no .env entry, no private dataset folder or manifest (no real, coco, open, hard, video, generated or corrupted data), no run output and no cache, and a scan of every text entry with the package secret patterns found no secret-like string. The .env.example entry lists MODEL_API_KEY with an empty value. The fresh clone itself has no .env file, .env is git-ignored, and no .env path is tracked by git.

## Boot probe in mock mode

The server was started once from the fresh clone with the mock provider, live calls off, host 127.0.0.1 and isolated port 8123, then stopped. Each route below was requested once.

| Route | Status | What came back |
| --- | --- | --- |
| GET /health | 200 | JSON with status ok and provider mock |
| GET / | 200 | Home page HTML, 8097 bytes |
| GET /app | 200 | Result page HTML, 32432 bytes |
| GET /guide | 200 | How it works page HTML, 9134 bytes |
| GET /api/info | 200 | Mode MOCK_FIXTURE, provider mock, planner heuristic, live off, min IoU 0.35, synthetic dataset, model role list |
| GET /api/examples | 200 | Two committed runs: DAVIS NEEDS_REVIEW (111 passed of 112, cost 0.28 USD) and COCO NO_GO (119 passed of 132, cost 0.33 USD) |
| GET /api/cases | 200 | Five synthetic red safety tag cases with labels hidden |
| GET /api/runs/a165cd6773cd433a/release-gate | 200 | Full gate JSON for the COCO run, decision NO_GO |
| GET /demo | 307 | Redirect to the home page at the same host and port |

After the server process was stopped, the health route no longer answered, which confirms the probe server is gone. No POST route that can spend was called. The stress, voice and audit routes were inspected in code only (see docs/API_CONTRACTS.md), because calling them live would need a key and the closeout rules forbid live calls.

## Free re-reads of saved runs

Command:

```powershell
$env:BLINDSPOT_RUNS_DIR = "fixtures/examples"
python -m blindspot_ci.cli release-gate --run a165cd6773cd433a
```

Result: decision NO_GO, exit code 1. Failing conditions: low light 6 of 10 (Wilson 0.313 to 0.832) and small object 19 of 24 (Wilson 0.595 to 0.908) against the 0.90 bar. Second annotator coverage and kappa FAIL (no agreement file). Training overlap FAIL (unknown). Live evidence PASS. Run hash 41fe524f59f9d124f74d11c6041b531ddafe2ad8bea412f1b02ecd2c9aa46794, 132 distinct image hashes.

Command:

```powershell
python -m blindspot_ci.cli release-gate --run 8f6003378706480a
```

Result: decision NEEDS_REVIEW, exit code 2. Absent has 0 scored cases. Small object 7 of 8 is noted as under the 10-case NO_GO minimum, so it is not a NO_GO. Training overlap FAIL (likely seen, UNVERIFIED). Live evidence PASS.

Command (mock fixture practice, runs folder unset so the new run writes to artifacts/runs):

```powershell
python -m blindspot_ci.cli experiment
python -m blindspot_ci.cli release-gate --run <printed run id>
```

Result: the experiment printed mode MOCK_FIXTURE with normal PASS, low_light FAIL_FALSE_NEGATIVE, alternate_view PASS, occluded UNKNOWN and absent PASS, scored 4 with 3 passed and 1 failed, no errors, estimated cost 0.0 USD. Gating the printed run id gave decision DEMO_ONLY, exit code 3, with the reason that run mode MOCK_FIXTURE is mock or fixture output, not model performance. The run id is random on each run; this closeout instance was b3f641ced01f4595 in the temp clone.

Command:

```powershell
python -m blindspot_ci.cli iou-sweep --run a165cd6773cd433a
```

Result: 73 box pairs rescored, 0 not rescored. Low light stays 6 of 10 at bars 0.25, 0.35 and 0.50, then falls to 4 of 10 at 0.75. Small object goes 19, 19, 18, 16 across the same bars. No condition flips against the 0.90 policy bar.

Command:

```powershell
python -m blindspot_ci.cli slice-tests --run a165cd6773cd433a
```

Result: low light 6 of 10 against 113 of 122 for the rest, difference -0.326, exact p 0.0087, Holm adjusted p 0.0612, label not distinguishable. Every other condition is also not distinguishable after correction. The report footer states that frames or photos are treated as independent observations.

Command:

```powershell
python -m blindspot_ci.cli coverage
```

Result: only the synthetic dataset loads in this checkout (5 cases, every core cell starred as underpowered). Coco, corrupted, generated, hard, open, real and video report no manifest. That confirms the private and open manifests are correctly absent from git, and that coverage claims need a checkout where the owner has built the sets.

## GitHub CI at the verified head

CI run 41536778372 for head 65cdb9dc36082bce3a036bb5d257d5e7ebdf7948 on main: completed with conclusion success. Both jobs passed: test (3.11) and test (3.13). Run page: https://github.com/fahaamqureshi/BLINDSPOT_CI/actions/runs/41536778372

The docs fixes from this closeout (the 331 count correction and this file pair) then landed on main as 10be6a251806ed856e1bf0d41ae009fbf30b6edc, a docs-only child of the verified head with no code change. CI run 41538664651 for that head also completed with conclusion success, both jobs passed. Run page: https://github.com/fahaamqureshi/BLINDSPOT_CI/actions/runs/41538664651 - the final main head and its CI link are confirmed again in the closeout delivery report, because this sentence itself ships in a follow-on docs commit.

## Live records read, not re-run

No live call was made in this closeout. The following are taken from docs/real-results.md and the committed run files, and they were cross-checked against the gate re-reads above where a saved run exists.

- Headline COCO run a165cd6773cd433a (LIVE_META, scripted MOCK_POLICY order): NO_GO, low light 6 of 10, small objects 19 of 24. Re-read for free above with the same verdict and hash.
- Headline DAVIS run 8f6003378706480a (LIVE_META, scripted MOCK_POLICY order): NEEDS_REVIEW, 111 of 112. Re-read for free above with the same verdict.
- Long video MOT20-03 corrected run e30e0efcc7ca43a7: NO_GO, 3 of 16 people followed on at least 90 percent of scored frames. Not re-run here, because the manifest and the raw stream are owner-local licence inputs kept out of git. See the limits section of the closeout report.
- Agent run e8830a46b8824796 (LIVE_META): 3 Muse planner calls and 3 SAM 3.1 calls on a 3 case fire hydrant subset, estimated cost 0.0165 USD, all 3 cases passed, gate NEEDS_REVIEW. No failure was found, so no agent-found failure is claimed from it.
- Agent run a23089bef4a840c8 (LIVE_META): 6 Muse muse-spark-1.3 planner calls and 6 SAM sam-3.1 calls, 12 budget calls in total, estimated cost 0.033 USD against a hard task cap of 0.10 USD. SAM missed cc_low_light_01, cc_low_light_02 and cc_low_light_04 at IoU 0.0; passes were cc_low_light_03 at 0.5789, cc_small_object_02 at 0.9323 and cc_small_object_01 at 0.8333. Gate on that 6 case run: NEEDS_REVIEW. The fixed gate on a165cd6773cd433a stayed NO_GO and the agent did not influence it.
- Project live estimate after run a23089bef4a840c8: 0.531 USD of a 4 USD authorized cap. Costs are BudgetGuard estimates, not billing receipts.

## Consistency sweep

README and every docs markdown file were searched for stale test counts, Render or hosted-live claims, Muse picks wording, and autonomous-agent wording.

- Fixed in this closeout: docs/explainer-simple.md said 273 automated tests in 4 places. The suite now collects 331, so those 4 lines were corrected to 331. This file and docs/SUBMISSION_CHECKLIST.md were rewritten with the 331 count and the new evidence.
- No Render claim exists in README or docs, and no doc claims a hosted live service. The deployment guide names Northflank as primary with Koyeb as fallback, and the explainer correctly says the guide is documented and ready to follow, not a hosted live service. No fix was needed.
- Muse picks and autonomous wording is correctly hedged everywhere it matters: the headline runs are stated to use a scripted order, the honest claim is agent assisted and not fully autonomous, and there is no proven benefit over random order yet. No fix was needed.
- Historical audit notes that name an older base commit or older page sizes were left as dated history, except for the two closeout files rewritten here. One display difference was noted without a code change: the app model list shows Muse Image while the README table shows Muse Image 1.0 (the API model id is muse-image-1.0 in both cases). It is listed as an open polish item in the closeout report, not fixed, because this closeout allows docs fixes only.

## Secret handling check

Existence only, no content read: the fresh clone has no .env file. The .env.example template lists the variable name MODEL_API_KEY with an empty value, plus provider, model, call, budget, cache and provenance settings. The name MODEL_API_KEY also appears in blindspot_ci/config.py, the CLI diagnostics and the package secret scan patterns. No key value was printed in any command in this closeout, and error text redaction is implemented in the Meta adapters.

## What was not run

- No live experiment, smoke call or planner call. Live history is taken from the committed run files and dated notes, not re-measured.
- Docker build: not run here. The image is defined in the Dockerfile and CI does not build it (see docs/deploy-and-readiness.md).
- Browser interaction beyond the HTTP probes above. Page behaviour is covered by the API and examples tests in the suite.
- The MOT20 long video was not rebuilt or re-scored here, because its manifest and raw stream are owner-local licence inputs that are not in this repository.
