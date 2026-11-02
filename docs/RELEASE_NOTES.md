# Audit release notes

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
