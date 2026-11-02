# Submission checklist

This file merges the owner checklist from `docs/demo-and-submission.md` with the artifact checks from this audit, without duplicating the demo wording (the demo lives in `docs/DEMO_SCRIPT.md`). Items marked UNVERIFIED have not been checked against the official Rules. Deadline on the event page: Nov 4 2026, 9:00 PM ET. Submit by 8:00 PM ET and re-open the link to confirm.

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

## Artifact presence (checked in this audit)

- [x] Project gate green at audit time: `python scripts/check.py` printed Summary PASS (ruff, pytest 273 passed, docs style, attribution, secrets). Re-run on the final main commit.
- [x] Committed example runs present: `fixtures/examples/a165cd6773cd433a.json` (COCO, NO_GO) and `fixtures/examples/8f6003378706480a.json` (DAVIS, NEEDS_REVIEW), both re-readable for free.
- [x] Long video policy present: `fixtures/policies/long-video.json`. Long video run files are local only by licence; keep the rebuild steps in `docs/long-video-test.md` with the submission notes.
- [x] Seven audit docs present: `docs/IMPLEMENTATION_STATUS.md`, `docs/DECISIONS.md`, `docs/TEST_RESULTS.md`, `docs/API_CONTRACTS.md`, `docs/EVALUATION_PROTOCOL.md`, `docs/DEMO_SCRIPT.md`, `docs/SUBMISSION_CHECKLIST.md`.
- [x] Demo path present: README quick start, the saved-run demo in `docs/DEMO_SCRIPT.md`, and the short script in `docs/demo-and-submission.md` (kept as the secondary copy; DEMO_SCRIPT is the primary).
- [x] Deployment guide present: `docs/free-deployment.md` (Northflank primary, Koyeb fallback, Cloudflare tunnel as temporary only).
- [ ] README first screen reads well: purpose, the NO_GO example, the four decisions with exit codes, and links to results, gate rules and deployment.
- [ ] No `.env` or API key in any package or image. Run `python scripts/package.py`, check the file list, and confirm the Docker build context excludes secrets.
- [ ] No AI attribution in git history on the final range.
- [ ] Evaluation card for each headline run downloaded and read once by a person.

## Deploy and video (owner accounts)

- [ ] Northflank: create the free Developer Sandbox (no card, no paid plan), connect the public GitHub repo on main with the root Dockerfile, expose port 8000 as web, set the health check to GET /health, set mock-only environment variables with the exact generated hostname in the allowed hosts value, and never set a key or live flag on the public service.
- [ ] After deploy, open /health, /, /app and /guide on the public URL, confirm /demo redirects to /, and open the saved COCO example in the app.
- [ ] Record the demo video from `docs/DEMO_SCRIPT.md`. Keep fixture steps labeled as fixture practice on screen or in narration. Never present a MOCK_FIXTURE number as a SAM result.
- [ ] Play the finished video on another device or account, outside this machine, end to end.
- [ ] Optional: add a free uptime monitor on the public health route with owner alerts.

## Final hour (Nov 4)

- [ ] Fetch origin, confirm CI is green on the final main commit, and re-run `python scripts/check.py` on that exact tree.
- [ ] Rotate the API key afterwards if the project folder was ever synced online or shared with a key in it.
- [ ] Submit by 8:00 PM ET (one hour before the deadline), then re-open the submission link and confirm every field, file and video plays.
- [ ] Write the final commit SHA and the CI run link into the submission notes.
