# Submission readiness

Date: 2026-11-03. Branch: codex/submission-readiness. Baseline and rollback point: da5bfc11fb4f525ef158e01274c7d50beda4d8ef. No reset, push, merge, deployment or submission was performed. No paid API call was made in this pass.

## Verdict

SUBMIT WITH DISCLOSED LIMITATIONS for a developer-stage local evaluation tool and mock demonstration. The source release candidate is demonstrable, builds into an installed wheel and passes its local checks. This is not an assertion that the participant account's final submission form is complete. Public multi-user live production is NOT READY: authentication, tenant isolation, durable cross-process accounting and hosted operational validation are absent.

The remaining submission gate is account-specific: confirm acceptance, registered track and theme, required links, recording constraints and final form fields in the signed-in portal. No requirement is inferred from an inaccessible form. The source ZIP and recording are prepared for owner review; no entry or receipt exists.

## Scope and evidence inventory

Repository discovery covered application and CLI entry points, 54 tracked package files, 33 tracked test files, 15 tracked scripts, build metadata, CI, Docker configuration, public data and fixtures, and 35 existing documentation files before this pass added release files. Private image contents, dotenv contents and credential values were excluded. The environment directory, caches, downloaded media and old artifacts are not production source and were not recursively modified or certified. This is an engineering audit, not a claim of complete penetration testing or semantic review of every private file.

| Component | Status | Evidence | Defect and result | Priority |
| --- | --- | --- | --- | --- |
| Frontend | VERIFIED | Chromium landing, fresh check, four tabs, image, note and mobile layout | Missing-image requests and invalid SVG dimensions corrected | P2 fixed |
| Backend | VERIFIED | Unit/API suite, isolated live HTTP server and restart audit | Malformed headers, invalid voice inputs and corrupt run shapes refused | P1 fixed |
| SAM integration | PARTIAL | Saved real calls in FULL_LIVE_MODEL_TEST.md and REAL_WORLD_VIDEO_DEMO.md; intercepted contracts | Standard importer frame indexes and seed boxes corrected | P0 fixed |
| Muse integration | PARTIAL | Earlier actual Spark tool calls and five-role execution, plus current offline regressions | No new paid inference claimed in this pass | Existing evidence |
| Agent workflow | VERIFIED | Bounded software tests and prior live traces | Per-call shared parent budget wired through both factories | P1 fixed |
| Dataset import | VERIFIED | PNG/JPEG, invalid/corrupt/oversized input, provenance and MOT alignment tests | One-based source indexes now map to zero-based video indexes | P0 fixed |
| Evaluation | VERIFIED | Photo, video, IoU threshold, gaps, unknown and absent regressions | Recovery episodes no longer bridge unscored or missing-frame gaps | P1 fixed |
| Release gate | VERIFIED | App, CLI and card video policy; fixed inventory checks | Video evidence now consistently uses the committed video policy | P1 fixed |
| Reports | VERIFIED | JSON and Markdown exports, restart and video cards | Frame identity digests no longer claim to be image hashes; confidence wording corrected | P1 fixed |
| Packaging | VERIFIED | Wheel smoke outside checkout and source ZIP rebuild | Explicit public assets added to wheels, source archive and Docker context | P1 fixed |
| Security | PARTIAL | Host/origin, budget, file, voice and advisory checks | Pillow decoder advisories addressed by version 13 | P0 fixed |
| Deployment | NOT_TESTED | Configuration inspected, local server executed | No Docker executable or hosted execution on this machine | External |

## Verified corrections

1. The API previously checked the shared budget before a whole run and charged after completion. Independent concurrent guards could each spend beyond the remaining estimate. Each child now reserves on the shared parent before a call. A rejected parent leaves child counters unchanged. Threaded regression permits exactly five USD 0.01 reservations under a USD 0.05 root. A real experiment runner with an intercepted provider stops after two USD 0.0025 reservations under a USD 0.005 root. Both agent factories propagate the parent. Voice, image and audit reservations use that same root. Refunds cannot release sibling reservations, and non-finite or negative reservations fail.
2. Malformed bracketed hosts, invalid ports, user-info hosts and host path fragments could evade validation or crash parsing. They now return 403. Malformed origins, origins with path components and different-scheme origins are refused. Voice requests validate case membership and content length before adapter construction. Invalid saved-run structures, mismatched IDs and trailing-newline IDs are refused. Run and review sidecars reject symbolic links; source packaging skips symbolic links.
3. The reusable MOT importer previously forwarded one-based annotation indexes and scored the starting label. It now records both source and zero-based indexes, excludes seed frames, converts seed endpoints to the API's inclusive convention, and excludes unobservable or absent references. A regression goes from imported labels through the request builder and intercepted video response to a correct following-frame score. Historical manifests must be regenerated; earlier long-video headline percentages are no longer promoted in README or guide.
4. Temporal miss runs previously joined across unscored intervals. They now censor at unknown, error and missing-frame gaps. Censored intervals are separate from observed recovery and observed end-of-clip failure. New temporal reports record the configured sampled inventory before inference. Frame identity hashes are distinguished from actual image hashes. New steps record valid image dimensions even without thumbnails; the UI does not request undefined image URLs.
5. The app, default CLI and evaluation card previously applied the photo policy to video evidence. They now select the committed video policy automatically for HUMAN_LABELED_VIDEO. Explicit CLI policies remain available. The current saved crowd run now consistently reports NO_GO because its occluded tracking is below the existing bar. No model score or policy threshold was softened.
6. The wheel previously omitted repository-level public assets that runtime loaders require. The build now copies an explicit list of public examples, fixture answers, synthetic labels/images and scenario data into package resources. Installed runtime loaders locate them without the source checkout. Private manifests and media are not bundled. A standalone verification script and CI smoke exercise the installed archive outside the checkout.
7. Pillow 12.3.0 matched decoder advisories. The old version constraint prevented its security update. The project now requires Pillow 13 and Python 3.11 or newer, and the local environment was updated and checked. Upstream evidence: [Pillow 13 security release](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html) and [supported Python versions](https://pillow.readthedocs.io/en/stable/installation/python-support.html). A complete installed runtime dependency closure, including optional SAM parsing and platform-selected Uvicorn extras, queried 24 versions against the [OSV API](https://google.github.io/osv.dev/api/). It returned zero advisory matches. This does not certify future resolutions or every possible vulnerability.
8. Tests disable dotenv loading before application imports, select mock and heuristic defaults, and clear inherited API credentials. Fake adapters remain intercepted tests. CI uses the full completion gate and wheel smoke on its Python 3.11 and 3.13 matrix. Current branch hosted CI has not run because this branch was not pushed.

## Exact validation outcomes

Full suite on Windows Python 3.13.15: 370 passed, 0 failed, 0 skipped, one external Starlette/httpx deprecation warning. This includes unit, API, contract, metric and agent tests; no invented separate integration-test count is given. Pillow test deprecations were removed. Only Python 3.13 is installed locally, so Python 3.11 execution is left to configured CI.

Required final command: `.venv/Scripts/python.exe scripts/check.py`, with DOTENV_DISABLED=1, BLINDSPOT_PROVIDER=mock, BLINDSPOT_PLANNER=heuristic and LIVE_API_ENABLED=false. The exact output is retained in artifacts/submission-audit/check-output.txt and is:

```text
PASS  ruff
PASS  pytest
PASS  docs style
PASS  attribution
PASS  secrets

Summary: PASS
```

Dependency consistency: `python -m pip check` returned `No broken requirements found.`

Installed-wheel verification returned:

```json
{"installed_wheel": "PASS", "public_assets": "PASS", "mock_checks": 5, "gate": "DEMO_ONLY", "paid_calls": 0}
```

The wheel verifier runs from a temporary directory with the wheel first on the module path, checks the actual imported package location, loads all public fixture images and both saved examples, runs five mock checks, opens the card and gate, and verifies live audit refusal. It does not require private datasets or make model calls. Source ZIP verification separately extracts the allowlisted archive, builds a wheel from that extracted source, and runs the same verifier. Local evidence stays under artifacts/submission-audit.

## Actual browser and HTTP journeys

Fresh browser run: 6a609abcaca0474f at http://127.0.0.1:8040. Landing navigation, new fixture run, all four result tabs, actual evidence image loading and reviewer note persistence passed. A 390 by 844 workspace had no horizontal overflow. No console errors were observed. The prerecorded backup is artifacts/submission-audit/submission-walkthrough.webm; its practice mode and scripted answers remain visible. It is not a recording of paid inference. Screenshots and browser-checks.json are beside it.

The isolated HTTP audit verified five configured fixture cases, equal repeated scores, five cache hits, DEMO_ONLY, invalid-step rejection, hostile host/origin rejection, twenty successful reads across four workers, five identical exports, process restart and saved report equality. Paid calls: zero. Timings in milliseconds: startup 1037.01, evaluation 29.97, cached evaluation 17.66, gate 8.48, card 2.12, twenty concurrent reads 31.37 total, restart 1038.07. These are single local measurements; peak memory, percentile latency, hosted behavior and production load are unmeasured.

Project CRUD, browser image upload, PDF export and server-side cancellation are not implemented. The actual workflow uses a dataset selector, local importer, local labeler, bounded run, evidence inspection, notes and Markdown/JSON export. No fictional project-creation workflow was added to the demonstration.

## Meta model and scientific status

Saved real SAM inference: verified in prior authorized execution. Saved real Muse Spark tool calling: verified in prior authorized execution. Fixture behavior: verified again in this pass. Human-reference real dataset evaluation: completed in prior execution. Other configured roles, Muse Image, Voice Transcribe and Wonder, have saved execution evidence in FULL_LIVE_MODEL_TEST.md. These statements do not imply every model call was repeated after this source change.

The latest crowd study used two clips, six seeded tracks and 929 video frames. Its 1,863 eligible target-frame scores matched an independent calculation from raw SAM boxes: 1,391 pass, 430 low overlap, 42 missing target, with 918 unscored subsequent slots and six seeds excluded. Estimated video request cost was USD 0.1858 in that earlier run. The broader preceding five-model test estimated about USD 0.61. Neither amount is an invoice; spending in this readiness pass was zero.

Limits remain: repeated frames are correlated, six tracks do not establish general reliability, training overlap is unknown, there is no second annotator, full-body references differ from visible-content boxes, and the original owner tray scenario has no real owner photographs. The model was evaluated, not repaired or certified. The prior 2,405-frame run needs its original indexing rechecked before reuse as a performance claim.

## Submission research and artifacts

The [official event page](https://dev.meta.ai/events/global-hackathon) was rechecked and lists November 4, 2026 at 9:00 PM ET. The [official waiver and rules](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver) rendered in the browser even though its text-only fetch returned Loading. The published project judging weights are Impact 30 percent, Meta AI tooling 25 percent, Technical depth and execution 20 percent, and Demo 25 percent. The project can demonstrate independent scoring, bounded Meta tooling and reproducible failures against those categories. Its registered track and theme are not inferred.

The rules link to https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit. In this browser that route redirects to https://cerebralvalley.ai/auth/login. Therefore accepted status, team representation, registered track/theme, form field limits, video duration, repository visibility and required URLs remain UNVERIFIED. Public rules are not evidence of this account's acceptance. No waiver was accepted and no form was submitted.

The public rules also require authority to grant broad rights over submitted materials and compliance with applicable open-source terms. The source package therefore omits all downloaded crowd footage, private photos, local reports and API state. The backup browser recording uses only repository-owned synthetic assets. This conservative packaging choice is not a legal determination that any particular third-party asset may be submitted.

Prepared outputs are dist/blindspot-ci-0.1.0.zip and the wheel under artifacts/submission-audit/wheels. The source archive, installed-wheel report, browser recording, screenshots and current documentation are reviewable locally. A publicly reachable demo, permitted final recording upload, participant-specific form completion and submission receipt are not present.

## Run commands and final clicks

Use a fresh source checkout or extract the source ZIP. Python 3.11 or newer is required.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:DOTENV_DISABLED = "1"
$env:BLINDSPOT_PROVIDER = "mock"
$env:BLINDSPOT_PLANNER = "heuristic"
$env:LIVE_API_ENABLED = "false"
python scripts/check.py
python -m blindspot_ci.cli serve
```

Open http://127.0.0.1:8000, click Try a practice check, keep Practice photos selected, and click Run check. Inspect the deliberate low-light miss in Test evidence, inspect the order under Technical details, save a typed note in Reviewer tools, and download the report from Overview. The result is DEMO_ONLY. Separately open a committed saved COCO example for recorded live scores; playback does not make new model calls.

## Remaining actions and production boundary

1. The owner must open the signed-in participant form, confirm account and project requirements, and verify the permitted final links and recording. No private account data can be inferred locally.
2. If the form requires a public URL, deploy and test the mock-only service in the owner's account. Docker was not executed here because Docker is unavailable; hosted uptime and security are not certified.
3. Review the source and permitted recording, then submit through the official portal and save its receipt. This audit does not authorize pushing, deployment or submission on the owner's behalf.

For a public live product, additional engineering is required: authentication and authorization, separate user data, durable shared spending and rate controls across processes and restarts, retention/backups, hosted monitoring and operational tests. The current in-process reservation fix does not replace those controls. There is one external test-client deprecation warning. No known reproduced catastrophic defect remains in the tested local workflow; undiscovered defects remain possible.

## Changed files

The exact tracked change list follows. Large local artifacts, media and helper outputs remain ignored. The final response records the commit SHA after the completion gate.

- .github/workflows/ci.yml
- AGENTS.md
- Dockerfile
- MANIFEST.in
- README.md
- blindspot_ci/agent.py
- blindspot_ci/api.py
- blindspot_ci/budget.py
- blindspot_ci/cli.py
- blindspot_ci/data.py
- blindspot_ci/experiment/card.py
- blindspot_ci/experiment/cases.py
- blindspot_ci/experiment/mot_importer.py
- blindspot_ci/experiment/release_gate.py
- blindspot_ci/experiment/reviews.py
- blindspot_ci/experiment/runner.py
- blindspot_ci/experiment/temporal.py
- blindspot_ci/factory.py
- blindspot_ci/providers/mock.py
- blindspot_ci/resources.py
- blindspot_ci/security.py
- blindspot_ci/web/guide.html
- blindspot_ci/web/index.html
- docs/API_INTEGRATION_VALIDATION.md
- docs/DEMO_SCRIPT.md
- docs/FINAL_AUDIT.md
- docs/FINAL_VERDICT.md
- docs/METRICS_VALIDATION.md
- docs/PERFORMANCE_RESULTS.md
- docs/REAL_WORLD_VIDEO_DEMO.md
- docs/RELEASE_NOTES.md
- docs/SECURITY_AUDIT.md
- docs/SUBMISSION_CHECKLIST.md
- docs/SUBMISSION_READINESS.md
- docs/USER_JOURNEY_TESTS.md
- pyproject.toml
- scripts/check.py
- scripts/package.py
- scripts/verify_wheel.py
- setup.py
- tests/conftest.py
- tests/test_budget_cache.py
- tests/test_iou_sweep.py
- tests/test_meta_extras.py
- tests/test_mot_importer.py
- tests/test_release_gate_api.py
- tests/test_security_reliability.py
- tests/test_slice_tests.py
- tests/test_temporal.py
