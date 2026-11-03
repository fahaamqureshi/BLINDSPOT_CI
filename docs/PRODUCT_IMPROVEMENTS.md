# Landing page and product improvements

Date: 2026-11-03. Branch: codex/product-landing. Baseline commit: 5768829789b81b50455fdb1cb96b3578d7899e18. Existing Python/FastAPI project retained. Work is local, mock-only and unpublished.

## Product decisions

The landing page now introduces the actual inspection problem, offers one primary practice action, shows a switchable fixture example, explains the scoring workflow, presents saved evidence and answers common questions. It uses restrained green and neutral colors, a consistent type hierarchy, a real project-owned synthetic illustration and native controls. No customer logos, testimonials, commercial savings or invented model results were added.

The preview reads actual shipped mock predictions and scores them with the existing evaluator. It makes no configured provider call, creates no run or cache entry, and is marked synthetic/scripted at the point of use. It remains offline even if the server is configured for a live provider. Its boxes use the source image's exact dimensions.

The workspace now lists recent local checks and can inspect every scored or unknown case, rather than only a gallery of failures. The case table opens the inspector. The reference label is called a fixture reference for synthetic data. Generated/corrupted and real dataset image routing uses dataset provenance rather than the current selection where supported. Download controls distinguish Markdown reports from run JSON. Requests time out with a recoverable message, and the dataset query from the landing-page link is honored.

## Defects fixed

| Finding | Root cause | Correction | Evidence |
| --- | --- | --- | --- |
| Reviewer file could replace displayed scores/source | Unvalidated extras dictionary merged over the saved run | Allowlist validated reviewer_notes and audit only | Regression failed with forged summary/mode, then passed |
| Malformed reviewer data could break notes/report UI | Valid JSON with wrong field types was accepted | Validate note list entries and audit shape before exposing them | New note still saves after a damaged sidecar |
| Saved checks difficult to find | Only example picker and manually supplied URLs existed | Bounded recent-run endpoint and visible links | Two created runs reopen; broken files and sidecars skipped |
| Only failed images inspectable | Evidence renderer only used failure gallery | Case inspector and case-table buttons | Normal, low-light, absent and unknown cases inspected in browser |
| Unknown and passing case descriptions unsuitable | Failure-only text reused for other statuses | Visibility-aware captions and fixture-reference wording | Unknown remains unscored, absent pass correctly has no box |
| Landing page did not explain the product through use | Intro and historical cards only | Real interactive fixture preview and a clear practice CTA | Four preview choices match shipped fixture outcomes |

## Validation

API tests were written and observed failing before each backend change. Preview initially returned 404; history initially returned 404; a forged reviewer sidecar initially replaced the original score summary. Final focused checks: 40 passed, 3 warnings in 1.60s. Final full explicit pytest: 344 passed, 0 failed, 0 skipped, 3 warnings in 8.65s. Warnings are the existing Starlette/httpx and Pillow deprecations. Ruff: All checks passed!

The first full run found the landing-page safety disclaimer wording had changed. The explicit not-a-safety-approval statement was restored without weakening the test.

scripts/audit_mock.py passed: run 1554f07c61504bd3, five tested, four scored, three passed, one intentional fixture miss, one unknown, no errors, DEMO_ONLY. Repeat scoring matched, five cached answers, 20 concurrent reads returned 200, report/run unchanged after restart, zero paid calls. Local startup 1596.47 ms, evaluation 34.06 ms, report 2.64 ms. This is not hosted or live-model performance. Raw audit evidence is local in artifacts/final-audit/evidence.json.

Browser: agent-browser Chromium at 1440 by 1000/1100, 768 by 1024 and 390 by 844. No horizontal document overflow or broken preview images was observed. Clear, low-light, obstructed and second-view selectors match the correct status and boxes. Saved evidence links open historical runs without inference. Workspace practice run 6bf3a4e37caa4364 appeared in recent checks; selecting normal and unknown displayed the correct reference/image. Markdown/JSON export, note persistence and error recovery were checked. Ordinary workflows reported no browser script errors.

Local screenshots: artifacts/product-review/landing-desktop.png, landing-low-light.png, landing-mobile.png, landing-tablet.png, landing-full.png, case-mobile.png, case-inspector.png and case-desktop.png. Intermediate captures may contain earlier wording. The final source and browser checks take precedence.

Final required gate command: python scripts/check.py.

```text
PASS  ruff
PASS  pytest
PASS  docs style
PASS  attribution
PASS  secrets

Summary: PASS
```

## Reference guidance

The five requested repositories were consulted as design/engineering references. No external installer, downloaded program, agent hook or third-party skill script was executed. Repository rules and user authorization remained controlling.

- [Superpowers systematic debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md): reproduce the failure, trace its cause, then verify a focused correction.
- [Matt Pocock skills](https://github.com/mattpocock/skills): clear product vocabulary and feedback loops. [TDD reference](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/SKILL.md): behavior checks at the public interface.
- [Anthropic frontend design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md): subject-specific visual decisions, concrete content and deliberate typography.
- [ECC frontend patterns](https://github.com/affaan-m/ECC/blob/main/skills/frontend-patterns/SKILL.md): explicit loading, success and error states. React-specific code was not imported into this plain-JavaScript app.
- [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill): accessible controls, responsive layout, visible feedback and consistent presentation.

## Changed files

- blindspot_ci/api.py
- blindspot_ci/experiment/reviews.py
- blindspot_ci/web/home.html
- blindspot_ci/web/index.html
- blindspot_ci/web/site.css
- blindspot_ci/web/landing.css
- tests/test_product_api.py
- README.md
- docs/API_CONTRACTS.md
- docs/DEMO_SCRIPT.md
- docs/PRODUCT_IMPROVEMENTS.md

## Open issues

Live SAM/Muse behavior and independent owner tag data remain unverified. The application still has no browser upload, project CRUD, authentication or guarantee of atomic server-wide live spending across concurrent runs. Private submission requirements and public photo redistribution rights still need owner review. These were not made verified by a visual redesign. No deployment, push or submission occurred.
