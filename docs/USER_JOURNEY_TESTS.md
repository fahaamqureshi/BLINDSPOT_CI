# User journey tests

## Current release candidate journey

The current mock server was tested at http://127.0.0.1:8040 with a real Chromium browser through agent-browser. The landing page opened the practice workspace, Run check created run 6a609abcaca0474f, and all four result tabs loaded. Actual fixture evidence images loaded. A reviewer note saved through the page persisted in the run sidecar. The 390 by 844 workspace had no horizontal overflow. No browser console errors were observed. Screenshots, browser-checks.json and submission-walkthrough.webm are local in artifacts/submission-audit.

The fixture workflow correctly returned DEMO_ONLY, one deliberate low-light failure, an alternate-view pass and an unscored obstructed case. These are software checks, not model performance. Project CRUD, browser photo import, PDF export and server-side cancellation are not implemented. Import and annotation are local commands. HTTP cache, repeated download, concurrent read and process restart checks passed through scripts/audit_mock.py.

Earlier browser observations follow.

Date: 2026-11-03. Real Chromium browser through agent-browser, local mock server at 127.0.0.1:8015. Browser checks are manual automation observations, separate from pytest counts. Browser commands sometimes reported a successful click without changing the native disclosure state; DOM activation was used to complete the journey. This is an automation limitation, not evidence that the control is broken.

| Journey | Result | Actual evidence |
| --- | --- | --- |
| A: New visitor | PASS | Home and guide headings/navigation loaded, example result rendered; no browser errors reported |
| B: Create inspection project | NOT_APPLICABLE | No project form, persistence model or project editing feature exists |
| C: Dataset import | PARTIAL | Local importer tests cover PNG/JPEG, corrupt/oversized files, EXIF, invalid boxes and provenance; no browser uploader exists |
| D: Start agent | MOCK_ONLY | Opened Run a new check, synthetic dataset, Run check; browser rendered run 1d525202ebaf467d with DEMO_ONLY |
| E: Investigate failure | PASS | Low-light fixture FAIL_FALSE_NEGATIVE; normal and absent PASS; occluded UNKNOWN |
| F: Recovery | MOCK_ONLY | alternate_view fixture PASS follows low-light failure; second preexisting image, no camera action or model repair |
| G: Release audit | PASS | Independent HTTP gate returned DEMO_ONLY; policy unit tests exercise other outcomes |
| H: Export | PASS | Actual Markdown attachment downloaded and reopened; JSON run available; no PDF/HTML report endpoint |
| I: Repeatability | PASS | Separate isolated server restarted; stored run fields and report bytes unchanged; second evaluation summary equal |

The complete scripted HTTP journey uses run 336018068fb54ae7 and artifacts/final-audit/evidence.json. Five cases, four scored, three passed, one deliberate fixture miss, one unknown, zero errors. These are software checks, not model performance.

Browser screenshots are local files artifacts/final-audit/desktop.png and mobile.png. Mobile viewport 390 by 844: document scroll width 375, no horizontal overflow. Screenshot inspected for readable result and mode notice. Browser console/errors commands emitted no errors. A full accessibility audit and every failing network request were not captured. Missing historical photos intentionally render labeled blank evidence panels, never invented photos.

The browser result table exposed misleading Found wording for absent cases and wording that denied an individual miss because the slice was small. Both were corrected. Desktop and mobile were rerun after the wording change. Project creation, direct upload, cancellation button, independent real tag labels and live service outage journey remain unsupported or unverified. Existing bounded-loop tests cover cancellation and repeated tool failures at the Python level.
