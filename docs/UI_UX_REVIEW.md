# Workspace usability redesign

Date: 2026-11-03. Branch: codex/usable-workspace. Baseline commit: 369434b3d8edefc7710c25bd94670eec525b31d3. Scope is the existing web UI and its wording checks. Scoring, providers and release policy were not changed.

## Changes

- The workspace starts with a short introduction instead of automatically opening a historical live result.
- Photo selection, the test limit and Run check are visible in a settings panel.
- Saved examples are an explicit separate action, labeled as previously recorded evidence.
- Result counts precede four keyboard-accessible views: Overview, Test evidence, Technical details and Reviewer tools.
- A consistent light palette, smaller type, restrained cards and responsive spacing replace the dense page.
- Human notes appear first in reviewer tools. Unavailable live actions and read-only example notes are disabled.
- Failed requests recover the Run button. An invalid photo set prevents execution until a usable set is selected.
- Scripted inference is no longer marked as actual SAM usage in the session model list.
- Evidence images load eagerly because the old lazy image was detached until its load event, so it could remain a blank placeholder indefinitely.
- Thin samples use caution labels even when all tested cases pass. A high pass fraction does not imply sufficient release evidence.

## Browser evidence

Browser: agent-browser Chromium, local server at 127.0.0.1:8000. The server reported MOCK_FIXTURE, mock provider, heuristic planner and live disabled before mutations. No live call was made. Only newly created fixture runs received reviewer notes. Existing dataset-generation buttons were not executed because they can replace a local derived dataset.

| Check | Result | Evidence |
| --- | --- | --- |
| First visit | PASS | Intro visible, settings available, no unexpected old result |
| Practice workflow | PASS | Five tests, three pass, one deliberate miss and one unknown; DEMO_ONLY |
| Result source and counts | PASS | Counts from actual run; practice source distinguished from saved live examples |
| Photo evidence | PASS | Synthetic failure image loaded with original human-box overlay |
| Tabs and keyboard | PASS | Selected view matches visible panel; ArrowRight moves focus and selection |
| Human note | PASS | Saved a note on run 9d494ba90f4b45d2 and received Note saved |
| Saved example | PASS | COCO example opened explicitly: 132 tests, 119 passed, 13 failed |
| Report | PASS | Actual card response contained the active run ID |
| Simulated connection failure | PASS | Browser fetch was temporarily rejected; error appeared and button recovered |
| Invalid dataset | PASS | Actual unknown-dataset response blocked Run; selecting synthetic restored it |
| Disabled live controls | PASS | Image generation, voice and audit unavailable in practice mode |
| Mobile and tablet | PASS | 390 by 844 and 768 by 1024, no horizontal document overflow |
| Desktop | PASS | 1440 by 1000, settings and workspace remain side by side |
| Browser script errors | PASS | None reported during ordinary workflows |

Raw screenshots remain local in artifacts/final-audit: ux-before.png, ux-workspace.png, ux-result.png, ux-evidence.png, ux-mobile-start.png, ux-mobile-result.png, ux-tablet.png and ux-home.png. Some screenshots show intermediate wording; final browser checks confirm the completed behavior. Existing API and release-gate HTML checks were updated to the new next-step heading.

## Validation and limits

Final required gate: python scripts/check.py. Successful output:

```text
PASS  ruff
PASS  pytest
PASS  docs style
PASS  attribution
PASS  secrets

Summary: PASS
```

The first regression run found one test expecting the former heading What to fix; its expectation now follows What to do next. No scoring assertion was weakened. This UI pass does not add project CRUD, browser uploads, authentication, live evidence or new model performance claims. Previously recorded submission blockers remain open.

Changed files: blindspot_ci/web/index.html, blindspot_ci/web/site.css, blindspot_ci/web/home.html, blindspot_ci/web/guide.html, tests/test_api.py, tests/test_release_gate_api.py, README.md, docs/DEMO_SCRIPT.md and docs/UI_UX_REVIEW.md.
