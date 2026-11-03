# Audit release notes

## Current readiness corrections, 2026-11-03

- Shared estimated spending is reserved before each call across concurrent in-process runs.
- Invalid request headers, voice cases, saved reports and linked files fail without unintended paid work.
- Standard MOT import now uses zero-based API frame indexes and excludes the seed and unobservable references.
- Video recovery episodes stop at unscored gaps, and video gate selection is consistent across app, CLI and cards.
- Missing thumbnails no longer create undefined image requests or invalid SVG dimensions.
- The wheel bundles only explicit public fixture assets and is checked outside the source tree.
- Pillow 13 security fixes are required; Python minimum is now 3.11.
- CI includes documentation, attribution, secret-pattern, source test and installed-wheel checks without live credentials.

The supported release remains a local single-user evaluation tool and public mock demonstration. Public multi-user live operation and participant-specific submission requirements are not verified. See SUBMISSION_READINESS.md.

Date: 2026-11-03. Existing product retained. No push, merge, deployment or submission.

- Correct full-precision IoU threshold decisions.
- Reject comparisons across changed labels, inputs, target concepts, datasets and thresholds. Legacy provenance is explicitly unverified.
- Reject JSON array/null planner arguments safely.
- Record configured case inventories in both run formats; check new report coverage independently of planner choices.
- Preserve source URL, license and attribution through image import.
- Clarify positive/negative pass counts and small-sample failure wording in the result UI.
- Add a repeatable no-cost local HTTP, cache, download, concurrency and restart audit script.
- Add final audit, journey, metrics, API, security, performance and verdict records; retain historical results separately.

Known limitations: no project CRUD or browser photo upload, no live validation in this audit, no new owner tray data, legacy gate inventories absent, single-object case scoring rather than detection AP, no authentication, no verified hosted release, and private submission rules still unverified. See FINAL_AUDIT.md and FINAL_VERDICT.md.
