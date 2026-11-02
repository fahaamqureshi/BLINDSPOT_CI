# Submission checklist

## Final audit update, 2026-11-03

The [official Meta page](https://dev.meta.ai/events/global-hackathon) confirms November 4, 2026 at 9:00 PM ET, which is November 5 at 7:00 AM in Karachi. The [organizer page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) agrees. Private participant rules and the submission form were inaccessible in this audit; the public waiver returned Loading. Application fields are not submission requirements.

| Requirement or artifact | State | Remaining action |
| --- | --- | --- |
| Public deadline | VERIFIED | Recheck participant portal for changes |
| Indie priorities | VERIFIED | Creativity, technical ambition and functionality |
| Push the Frontier description | VERIFIED | Fits manufacturing reliability; registered theme unknown |
| Eligibility, acceptance, registered track/theme | UNVERIFIED | Owner must check accepted-participant account |
| Required models and usage minimum | UNVERIFIED | Read official rules |
| Title, description and team fields | UNVERIFIED | Read actual form constraints |
| Source delivery and repository visibility | UNVERIFIED | Confirm public/private requirement |
| Video length, format, demo URL, screenshots | UNVERIFIED | Confirm rules; no hosted demo verified |
| Disclosure and third-party asset terms | UNVERIFIED | Check rules and redistribution rights |
| Code, README, license and mock demonstration | PREPARED | Local validation only |
| Final audit documents | PREPARED | See FINAL_AUDIT.md and FINAL_VERDICT.md |
| Submission receipt | MISSING | Nothing submitted |

Suggested evidence: creativity is separating exploratory tests from deterministic scoring; ambition is bounded tools and segmentation parsing; functionality is the mock failure, follow-up, unknown handling, export and restart. Live decisions need verification before inclusion. Public sources do not establish the account's selected track or judging weights.

This file merges the owner checklist from docs/demo-and-submission.md with the artifact checks from the closeout verification, without duplicating the demo wording (the demo lives in docs/DEMO_SCRIPT.md). Items marked UNVERIFIED have not been checked against the official Rules. Deadline on the event page: Nov 4 2026, 9:00 PM ET. Submit by 8:00 PM ET and re-open the link to confirm.

Closeout verification: 2026-11-03 on origin main 65cdb9dc36082bce3a036bb5d257d5e7ebdf7948, fresh clone in mock mode, no live call made. Full commands and outputs are in docs/TEST_RESULTS.md.

## Rules and track (owner, UNVERIFIED)

- [ ] Read the official Rules end to end. Required fields, eligibility, judging weights and any model-use terms are UNVERIFIED until then.
- [ ] Choose the track: Indie or Startup (undecided today). Record the choice and why here before submitting.
- [ ] Confirm the video length limit and the repository and write-up requirements against the Rules, not against secondary posts.
- [ ] Confirm what may be shown publicly: COCO photo licence before showing COCO photos, DAVIS research-use limits, MOT20 non-commercial terms (never redistribute, never commit).

## Evidence blockers (owner)

- [ ] Take the owner photos: 28 or more photos of the red safety tag on the maintenance tray, taken after the model release, across normal, low_light, small_object, truncated and absent. Until they exist, the training overlap check keeps GO_CANDIDATE out of reach and the tray story stays fixture practice.
- [ ] Label every photo with the local label tool (named annotator on each label), import them, and keep the private manifest out of git.
- [ ] Find a second annotator for at least 30 percent of cases, run compare-labels, and keep the agreement file for the gate. Target kappa at least 0.60.
- [ ] Run one fresh live experiment on the owner set and gate it. Budget first with the free commands; keep the run inside the stated caps.
- [ ] Check the SAM 2 and SAM 3 papers before quoting any training-overlap claim (DAVIS likely seen is UNVERIFIED today).

## Artifact presence (checked in this closeout)

- [x] Project gate green on the verified head: python scripts/check.py printed Summary PASS (ruff, pytest 331 passed, docs style, attribution, secrets) from a fresh clone at 65cdb9dc36082bce3a036bb5d257d5e7ebdf7948. Re-run on the final main commit before submitting.
- [x] GitHub CI green at the same head: run 41536778372, jobs test (3.11) and test (3.13) both success. Run page: https://github.com/fahaamqureshi/BLINDSPOT_CI/actions/runs/41536778372 - the closeout docs then landed as main head 10be6a251806ed856e1bf0d41ae009fbf30b6edc with CI run 41538664651 also green (https://github.com/fahaamqureshi/BLINDSPOT_CI/actions/runs/41538664651). Re-confirm once more on the final main commit and write that run link into the submission notes.
- [x] Committed example runs present: fixtures/examples/a165cd6773cd433a.json (COCO, NO_GO, gate exit 1) and fixtures/examples/8f6003378706480a.json (DAVIS, NEEDS_REVIEW, gate exit 2), both re-readable for free. A fresh mock fixture run gates to DEMO_ONLY with exit 3.
- [x] Long video policy present: fixtures/policies/long-video.json. Long video run files are local only by licence; keep the rebuild steps in docs/long-video-test.md with the submission notes.
- [x] Audit and closeout docs present: docs/IMPLEMENTATION_STATUS.md, docs/DECISIONS.md, docs/TEST_RESULTS.md, docs/API_CONTRACTS.md, docs/EVALUATION_PROTOCOL.md, docs/DEMO_SCRIPT.md, docs/SUBMISSION_CHECKLIST.md.
- [x] Demo path present: README quick start, the saved-run demo in docs/DEMO_SCRIPT.md, and the short script in docs/demo-and-submission.md (kept as the secondary copy; DEMO_SCRIPT is the primary).
- [x] Deployment guide present: docs/free-deployment.md (Northflank primary, Koyeb fallback, Cloudflare tunnel as temporary only).
- [x] Submission package checked from the fresh clone: python scripts/package.py wrote 143 files, with no .env entry, no secret-like string, and no private dataset folder or manifest. The Docker build context check stays an owner step below, because Docker was not run in this closeout.
- [x] Stale test count fixed: docs/explainer-simple.md now says 331 automated tests (was 273 in 4 places). No Render or hosted-live claim exists in README or docs, and Muse picks wording is hedged as agent assisted, not fully autonomous.
- [ ] README first screen reads well: purpose, the NO_GO example, the four decisions with exit codes, and links to results, gate rules and deployment. Owner to confirm by reading the rendered page once.
- [ ] No .env or API key in any package or image. The ZIP half is checked above; still confirm the Docker build context excludes secrets when the image is next built.
- [ ] No AI attribution in git history on the final range. The local gate attribution check passed on the verified head; re-check after the closeout docs land on main.
- [ ] Evaluation card for each headline run downloaded and read once by a person.

## Live evidence on record (not re-run in this closeout)

- Headline runs used a scripted MOCK_POLICY order, not the agent: COCO a165cd6773cd433a NO_GO and DAVIS 8f6003378706480a NEEDS_REVIEW. Never present the agent runs as the source of these verdicts.
- Agent run e8830a46b8824796 (LIVE_META, 3 Muse calls plus 3 SAM calls, estimate 0.0165 USD): all 3 cases passed, gate NEEDS_REVIEW, no agent-found failure claimed.
- Agent run a23089bef4a840c8 (LIVE_META, 6 Muse muse-spark-1.3 calls plus 6 SAM sam-3.1 calls, estimate 0.033 USD, hard task cap 0.10 USD): misses cc_low_light_01, cc_low_light_02 and cc_low_light_04 at IoU 0.0, passes cc_low_light_03 at 0.5789, cc_small_object_02 at 0.9323 and cc_small_object_01 at 0.8333, gate NEEDS_REVIEW. The fixed COCO gate stayed NO_GO without agent influence.
- Project live estimate after run a23089bef4a840c8: 0.531 USD of a 4 USD authorized cap. Estimates are BudgetGuard estimates, not billing receipts. Headline separation stays: the agent explores, the fixed gate decides.

## Deploy and video (owner accounts)

- [ ] Northflank: create the free Developer Sandbox (no card, no paid plan), connect the public GitHub repo on main with the root Dockerfile, expose port 8000 as web, set the health check to GET /health, set mock-only environment variables with the exact generated hostname in the allowed hosts value, and never set a key or live flag on the public service.
- [ ] After deploy, open /health, /, /app and /guide on the public URL, confirm /demo redirects to /, and open the saved COCO example in the app.
- [ ] Record the demo video from docs/DEMO_SCRIPT.md. Keep fixture steps labeled as fixture practice on screen or in narration. Never present a MOCK_FIXTURE number as a SAM result.
- [ ] Play the finished video on another device or account, outside this machine, end to end.
- [ ] Optional: add a free uptime monitor on the public health route with owner alerts.

## Final owner-only list

Only the owner can do these. Everything else above is either checked in this closeout or is a free re-read.

- Read the official Rules, choose Indie or Startup, and confirm video length, write-up fields, eligibility and public-display licences (COCO photos, DAVIS research use, MOT20 non-commercial).
- Take 28 or more owner tray photos after the model release, label them with a named annotator, and import them with the private manifest kept out of git.
- Recruit a second annotator for at least 30 percent of cases, run compare-labels (target kappa at least 0.60), and keep the agreement file.
- Run one fresh live experiment on the owner set inside the stated caps and gate it, then read each headline evaluation card once as a person.
- Check the SAM 2 and SAM 3 papers before quoting the DAVIS training-overlap note.
- Deploy the mock demo on Northflank (or the Koyeb fallback), verify the public routes, record the demo video from docs/DEMO_SCRIPT.md, and play it end to end on another device or account.
- In the final hour, re-run the gate and CI checks on the final main commit, confirm no secret is in any package or image, submit by 8:00 PM ET, re-open the submission link, and rotate the API key afterwards if the project folder was ever synced or shared with a key in it.

## Final hour (Nov 4)

- [ ] Fetch origin, confirm CI is green on the final main commit, and re-run python scripts/check.py on that exact tree.
- [ ] Rotate the API key afterwards if the project folder was ever synced online or shared with a key in it.
- [ ] Submit by 8:00 PM ET (one hour before the deadline), then re-open the submission link and confirm every field, file and video plays.
- [ ] Write the final commit SHA and the CI run link into the submission notes.
