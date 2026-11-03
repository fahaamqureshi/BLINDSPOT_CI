# Frontend review and cleanup

Reviewed November 4, 2026, Pakistan time. Scope: the main landing page, workspace, shared styles and guide. Baseline: 095792d13c9a59d2ee1244e327211817bbfb3f8c. Branch: codex/frontend-cleanup. No backend scoring, release policy, provider or budget behavior changed.

## Sources consulted

The owner requested agent-browser and popular GitHub design skills. Agent-browser core and exploratory-testing guidance were used for the browser review. Repository popularity was checked through the official GitHub API during this session. These are repository stars, not individual skill ratings or a claim that every design repository was compared.

| Repository | Stars at review | Use |
| --- | --- | --- |
| https://github.com/anthropics/skills | 187043 | Frontend-design guidance: deliberate hierarchy, clear copy, restrained visual structure and browser critique. |
| https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 144697 | Reference guidance for readable controls, touch targets, progressive disclosure and responsive layout. |
| https://github.com/pbakaus/impeccable | 101328 | Popularity compared; no implementation code adopted. |

The first two were the most-starred of the three compared. Their guidance was adapted manually to the existing plain HTML, CSS and JavaScript stack. No GitHub installer, downloaded source script or new frontend dependency was executed. The UI UX Pro Max search scripts were not run, so no generated design-system search result is claimed.

## Findings and fixes

| Finding | Change | Evidence |
| --- | --- | --- |
| Mobile result tabs required horizontal scrolling. | Four visible tabs in a two-column mobile layout, with existing keyboard navigation retained. | All four tab bounds fit 320-pixel and 390-pixel viewports. |
| Setup, saved examples and recent history competed with the current result. | A single page heading, compact setup, collapsible examples and history. Setup collapses after a result loads on mobile. | Browser setup-panel state is closed on a saved mobile result. |
| The inspected failure was also rendered as a second full image card. | Compact failed-case shortcuts and one main inspector. | One figure exists in the evidence panel after selection. |
| Reviewer notes initially targeted the first case even when the inspector showed a failure. | Both case selectors now share the selected case, including changes from either selector. | Inspecting low_light selects low_light for the note. A typed note saved with that exact case ID. Selecting alternate_view from notes also changes the inspector. |
| Long photo-set labels were clipped in the setup selector. | Short, readable names such as Practice drawings and Generated variants. Technical IDs remain in run details and exports. | Desktop and mobile browser review. |
| Empty sets could offer an enabled Run check action. | An empty case response disables Run check and explains how to proceed. | A controlled empty-case response simulation produced disabled=true and the expected explanation. Real generated fixtures in this checkout contain two cases; those remain runnable. |
| Landing content repeated the workflow and used many small labels. | Shorter copy, fewer repeated sections, larger control and disclosure text, calmer spacing and consistent colors. | Before and after desktop and mobile screenshots. |
| Narrow-screen header and headline became cramped at 320 pixels. | A smaller narrow-screen heading, a single-line workspace action and less secondary copy. | Interactive element bounds fit the viewport after adjustment. |

The color system uses a neutral light background, white surfaces, dark green text, a teal action color and semantic amber or red only where relevant. System fonts avoid a new network dependency. The guide shares the same readable foundation. Mock and recorded-live source labels, unknown outcomes and sample-size limits remain explicit.

## Validation

The local audit server uses DOTENV_DISABLED=1, BLINDSPOT_PROVIDER=mock, BLINDSPOT_PLANNER=heuristic and LIVE_API_ENABLED=false. MODEL_API_KEY is removed from its process environment. Browser actions created only deterministic practice results or opened existing saved reports. No new paid model call occurred.

Browser checks covered the landing preview conditions, reference-label visibility, a five-case practice check, result views, failed-case selection, reviewer-note save and case synchronization, arrow and Home or End tab navigation, saved DAVIS result loading, mobile setup collapse, tab bounds, empty-set feedback and browser errors. The empty-set case used an explicit local response stub after the browser routing attempt did not intercept; it is not evidence that the real generated set is empty.

Desktop captures use 1440 by 1000. Mobile checks use 390 by 844 and 320 by 740, including interactive bounds rather than relying only on hidden horizontal overflow. No reported JavaScript error was observed during the tested flows. Both page scripts passed Node syntax checks. Git diff whitespace validation passed. Full pytest passed with one existing external Starlette and httpx deprecation warning.

Screenshots and local validation evidence are in artifacts/frontend-refresh. The required final gate is scripts/check.py in mock mode. The public wheel is rebuilt and checked outside the checkout with live access disabled. Exact final outputs and commit SHA are retained in the delivery report and final response.

## Changed files

- blindspot_ci/web/home.html: shorter entry copy, less repetition, plain-language saved verdicts and focusable main landmark.
- blindspot_ci/web/landing.css: landing typography, spacing, controls and responsive layout.
- blindspot_ci/web/index.html: workspace structure, compact evidence selection, note context, empty-set feedback, shorter labels and accessible form descriptions.
- blindspot_ci/web/site.css: shared palette, guide styling and the workspace design system.
- blindspot_ci/web/guide.html: updated style version, home wordmark link and main landmark focus.
- docs/FRONTEND_REVIEW.md: this report.

## Limits

This review does not establish general model performance or production readiness. Live model actions, microphone hardware, new uploads and public multi-user deployment were not exercised. Existing saved examples can show a box-only fallback where a photo is not part of the distributable. Source media and earlier recorded demo movies were not regenerated by this frontend task. No push, deployment or submission occurred.
