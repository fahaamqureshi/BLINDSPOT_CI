# Test results

Audit date: 2026-11-03. Checkout: worktree on branch ao/repo-audit/root, rebased onto origin main 632f283 before these docs were written. Python environment: the project virtual environment already present in the worktree. Mode: mock only. No live API call was made and no secret value was read.

This file records exact commands and what they printed. A result without output is not claimed anywhere in the audit docs.

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

The gate runs ruff, pytest, a docs style scan over README and docs markdown, a git attribution scan, and a secret scan from `scripts/package.py`. The style scan bans em dashes, ellipsis characters, three dots, asterisks and emojis in docs prose (fenced code and inline code are excluded). These seven audit docs were written to pass the same scan.

## Lint and tests on their own

Command:

```powershell
python -m ruff check blindspot_ci scripts tests
```

Output: All checks passed.

Command (fresh temp folder, cache disabled):

```powershell
python -m pytest --basetemp=<temp>\bc-audit-pytest2 -p no:cacheprovider
```

Output tail: 273 passed in 5.71s. Exit code 0.

Collected tests by file (from collect-only): test_agent 1, test_api 7, test_budget_cache 4, test_check 8, test_cli 7, test_cluster_ci 8, test_coverage 8, test_custom_scenario 7, test_evaluator 1, test_examples_api 4, test_experiment_api 6, test_experiment_cases 17, test_experiment_runner 21, test_experiment_scoring 14, test_importer 12, test_iou_sweep 4, test_labeler 3, test_live_adapter 23, test_meta_extras 24, test_mot_importer 5, test_package 4, test_planner 11, test_release_gate 26, test_release_gate_api 3, test_replay 4, test_sam_video 18, test_slice_tests 4, test_temporal 19. Total 273.

Coverage note: the suite covers scoring, the gate, planners, the API, the video parser, corruptions through the API tests, budget and cache, packaging and the checker itself. It runs fully offline in mock mode, so a green suite proves the code path, not live model behaviour.

## Boot probe in mock mode

The server was started once with the mock provider, live calls off, port 8019, and the runs folder pointed at the committed examples. Each route below was requested once and the server was then stopped.

| Route | Status | What came back |
| --- | --- | --- |
| GET /health | 200 | JSON with status ok and provider mock |
| GET / | 200 | Home page HTML, 6525 bytes |
| GET /app | 200 | Result page HTML, 29567 bytes |
| GET /guide | 200 | How it works page HTML, 8771 bytes |
| GET /api/info | 200 | Mode MOCK_FIXTURE, provider mock, planner heuristic, live off, min IoU 0.35, synthetic dataset, model role list |
| GET /api/examples | 200 | Two committed runs: DAVIS NEEDS_REVIEW (111 passed of 112, cost 0.28 USD) and COCO NO_GO (119 passed of 132, cost 0.33 USD) |
| GET /api/cases | 200 | Five synthetic red safety tag cases with labels hidden |
| GET /api/runs/a165cd6773cd433a/release-gate | 200 | Full gate JSON for the COCO run, decision NO_GO |
| GET /demo | 307 | Redirect to the home page |

No POST route that can spend was called. The stress, voice and audit routes were inspected in code only (see `docs/API_CONTRACTS.md`), because calling them live would need a key and the audit rules forbid live calls.

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

## Secret handling check

Existence only, no content read: this worktree has no `.env` file. The `.env.example` template lists the variable name MODEL_API_KEY with an empty value, plus provider, model, call, budget, cache and provenance settings. The name MODEL_API_KEY also appears in `blindspot_ci/config.py`, the CLI diagnostics and the package secret scan patterns. No key value was printed in any command in this audit, and error text redaction is implemented in the Meta adapters.

## What was not run

- No live experiment, smoke call or planner call. Live history is taken from the committed run files and dated notes, not re-measured.
- Docker build: not run here. The image is defined in the Dockerfile and CI does not build it (see `docs/deploy-and-readiness.md`).
- Browser interaction beyond the HTTP probes above. Page behaviour is covered by the API and examples tests in the suite.
