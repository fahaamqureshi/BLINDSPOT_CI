# Final product audit

## Current submission-readiness pass

The current repository audit is recorded in [SUBMISSION_READINESS.md](SUBMISSION_READINESS.md). It covers the installed wheel, shared pre-call budget reservations, malformed requests, video frame alignment, seed exclusion, gap-censored recovery, consistent video policy selection, Pillow 13 security fixes, browser use and source packaging. The local full suite passes 370 tests. No paid call was made in this pass. Earlier live evidence is linked in FULL_LIVE_MODEL_TEST.md and REAL_WORLD_VIDEO_DEMO.md.

The audit below is an earlier baseline, not the current release verdict.

Audit date: 2026-11-03. Mode: mock only. Baseline commit: f6ff94dee434abf882954c01ffe1bad27e51a805. Branch: codex/final-product-audit. Historical live claims in other documents were not independently reproduced in this audit.

| Component | Status | Evidence | Defect | Priority |
| --- | --- | --- | --- | --- |
| Frontend | VERIFIED | Browser home, guide, saved example and new synthetic result | Sample wording and negative-case heading corrected | P2 fixed |
| Backend | VERIFIED | Running Uvicorn, HTTP smoke, restart, pytest | No reproduced mock blocker | None |
| SAM integration | PARTIAL | Official request documentation and offline contract tests | No authorized live validation | P0 external |
| Muse integration | PARTIAL | Tool contract tests and official documentation | No live decisions validated in this audit | P0 external |
| Agent workflow | MOCK_ONLY | Failure triggers alternate-view fixture; bounded-loop tests | JSON array or null arguments could crash planner | P1 fixed |
| Dataset import | VERIFIED | Importer, label validation and EXIF tests | Source URL, license and attribution dropped | P1 fixed |
| Evaluation | VERIFIED | IoU, unknown, absent, interval and negative fixture tests | Rounding before threshold could create false pass | P0 fixed |
| Release gate | PARTIAL | Four policy statuses tested; mock run DEMO_ONLY | New reports now record and check configured inventory; legacy reports lack it | P1 fixed for new runs |
| Reports | VERIFIED | Markdown attachment and JSON retrieval, restart equality | No PDF export implemented | None |
| Security | PARTIAL | Host, origin, path, live refusal, package scan tests | No authentication; shared live spending accounting remains unsuitable for concurrent public use | P1 open |
| Deployment | NOT_TESTED | Dockerfile and CI inspected; local wheel built | No hosted deployment or container execution | P1 external |

## Architecture and actual scope

Python CLI enters blindspot_ci/cli.py. FastAPI in api.py serves plain HTML, CSS and browser JavaScript. There is no frontend framework or frontend build. Providers are mock and Meta; SAM parsing uses meta-sam-parser. Both a case-selecting planner and a separate nine-tool bounded agent loop exist. The web Run check route uses the case planner, not the nine-tool loop. No model is the scorer.

Datasets are manifests with one human box or absent/unknown visibility per case. Import is a local command and annotation is a separate local labeler. There is no project CRUD, project name form, browser photo upload or database. Runs, cache and reviewer extras use JSON files, with atomic writing helpers. Reports are saved JSON and downloadable Markdown cards.

Settings default to mock, heuristic, synthetic, live off, 16 calls and a USD 5 estimate cap. Meta transport has finite timeout and retries. No startup inference is needed. Authentication is absent. Host and same-origin guards support a local single-user prototype. CI installs dev dependencies and runs ruff and pytest on Python 3.11 and 3.13 without live credentials.

## Fixes and regression evidence

1. scoring.py compared a four-decimal rounded IoU to the threshold. It now compares full precision. A just-below-threshold regression test fails under the old implementation and passes now.
2. regression.py paired only case IDs. It now rejects changed dataset, threshold, image hash, ground truth or concept and duplicate IDs. Incomplete legacy provenance yields UNVERIFIED rather than a regression verdict. Model identifiers and planner prompts remain recorded in the original reports and may legitimately differ in a model comparison.
3. planners.py assumed decoded JSON was an object. Arrays and null are now rejected as PlannerError; both cases have offline regression tests.
4. Both runner report formats now include configured_case_ids. Gate checks reject omitted, extra or duplicated cases for those new reports. A strong all-pass fixture with an omitted case gives NEEDS_REVIEW. Legacy reports cannot establish full configured-suite coverage.
5. importer.py now preserves supplied source_url, license and attribution. JPEG regression test checks the manifest values.
6. The result table now says Passed, including negatives. A tiny sample does not erase an individual failure; the wording now separates those concepts.

Focused fix validation: 83 passed in 2.45s. Full baseline: 331 passed, 3 warnings in 7.58s. Full intermediate regression: 340 passed, 3 warnings in 6.43s. Final gate output is recorded in FINAL_VERDICT.md.

## Execution evidence and limits

scripts/audit_mock.py launches an isolated mock server, runs all five synthetic cases, compares repeat scoring, checks cache provenance, downloads a card, exercises invalid steps and host/origin rejection, performs 20 reads with four workers, repeats five downloads and restarts the process. Evidence is artifacts/final-audit/evidence.json. It terminates only its own server. This is local evidence, not a hosted load test.

No live inference, private portal submission, push, merge or deployment occurred. No API key or dotenv file was opened. DOTENV_DISABLED=1 was used for audit processes. Existing tests use fake credentials and intercepted transport.

Open items: live integration and genuine model-driven behavior, fresh owner tray photographs and independent labels, private official rules, redistribution rights, hosted deployment and multi-user controls. See FINAL_VERDICT.md for the release decision.

## Changed files

- AGENTS.md and README.md
- blindspot_ci/experiment/agent_loop.py
- blindspot_ci/experiment/importer.py
- blindspot_ci/experiment/planners.py
- blindspot_ci/experiment/regression.py
- blindspot_ci/experiment/release_gate.py
- blindspot_ci/experiment/runner.py
- blindspot_ci/experiment/scoring.py
- blindspot_ci/web/index.html
- scripts/audit_mock.py
- tests/test_experiment_runner.py
- tests/test_experiment_scoring.py
- tests/test_importer.py
- tests/test_release_gate.py
- docs/API_INTEGRATION_VALIDATION.md
- docs/DEMO_SCRIPT.md
- docs/FINAL_AUDIT.md
- docs/FINAL_VERDICT.md
- docs/METRICS_VALIDATION.md
- docs/PERFORMANCE_RESULTS.md
- docs/RELEASE_NOTES.md
- docs/SECURITY_AUDIT.md
- docs/SUBMISSION_CHECKLIST.md
- docs/USER_JOURNEY_TESTS.md
