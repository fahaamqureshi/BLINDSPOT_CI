# Demo and submission

## 90-second demo

Use a real run on the Open Images set (or your own labeled photos). Do the mock run only to explain the layout.

1. Start the app with `BLINDSPOT_PROVIDER=meta`, `LIVE_API_ENABLED=true`, `BLINDSPOT_DATASET=real`.
   Say: "This tests SAM 3.1 on one task and is not a safety approval."
2. Point at the mode badge (`LIVE_META`) and press Run experiment.
3. Walk through the trace: Muse's tool call and reason, the SAM masks on the photo, the yellow human
   label, the IoU and status.
4. Show the step where the result changes the next choice, for example a miss followed by the
   recovery photo you supplied.
5. Show the saved report: image hash, IoU, latency, cost. Say how many photos there are and what the
   threshold is.
6. Say plainly what you did not test. Never show a `MOCK_FIXTURE` number as a SAM result.

## Hackathon facts (checked 2026-10-31)

- Virtual, worldwide, selected participants. Tracks: Indie developer and Startup.
- Submission due Nov 4, 2026, 9:00 PM ET. Dates can change, so check the portal.
- Selected participants must accept the official rules. They are authoritative over this file.
- Pricing used for estimates: Muse Spark 1.3 Standard $1.25 per million input tokens, $4.25 per
  million output tokens; SAM 3.1 $2.50 per 1,000 images. Default spend cap here is $5 per run.
- Rules to keep: do not share keys, do not bypass rate limits, use Standard mode, keep Meta's labels
  on real outputs, use only authorized media.

## Verified live (2026-10-31)

- `muse-spark-1.3`: text call returned READY; ordered probes with a parsed reply.
- `sam-3.1`: 4 person boxes and 1 bus box on one sample photo; 1 image processed.

- Muse function calling through `/chat/completions` (`smoke-tools`): picked a case by tool call. The
  API accepts only `tool_choice: "auto"`.
- Full experiment run on the synthetic drawings (run 48925eb343ec406d, 9 calls, about $0.025): Muse
  chose 4 tests by tool call, SAM 3.1 ran each, Python scored them. SAM found nothing on 3 drawings
  (false negatives) and the absent case passed. This checks the plumbing only. It is not evidence
  about SAM on real photos.

- `scripts/live_models_check.ps1`: Muse Wonder replied, Muse Image returned an edited image, and
  Muse Voice Transcribe returned the exact sentence from a Windows text-to-speech WAV.
- `stress-gen` made 2 variants (low light, glare) of the synthetic `normal` drawing with Muse Image.
  `live_experiment.ps1 -Dataset generated` ran them (run f6fa80a1f7704b3e). SAM found nothing in
  either, scored as false negatives. Generated drawings are plumbing checks, not evidence.
- Web page, live: Run experiment on the generated dataset, and the model panel marked Muse Spark and
  SAM as used. A Muse Wonder audit was written for run f6fa80a1f7704b3e through the CLI.

- Real labeled photos (Open Images V7, 24 cases): 20 of 22 scored cases passed after two doubtful labels were adjudicated
  (20 of 24 before). The two failures are real false positives. Details and caveats in `docs/results-open-images.md`.
- Masks drawn over a real photo in the browser: the SAM mask follows a real hydrant and the human box
  agrees (IoU 0.988).
- Measured corruptions: 22 of 22 tested variants passed (the agent stopped at 22 of 40).
- Agent versus random order: no evidence the agent beats chance on 24 cases (p 0.83).

Not yet verified live: any result on red safety tags on a maintenance tray (your own photos), and a
voice note recorded from a browser microphone (the voice endpoint is tested with a WAV file only).

## Using each model in the demo

1. Show the five model cards on the page and say what each does.
2. Muse Spark and SAM: run on real photos.
3. Muse Image: press Generate variants, run the generated set, and say these are stress tests with
   inherited boxes, not real photos.
4. Muse Voice Transcribe: on one failed case press Record voice note and say your verdict aloud.
5. Muse Wonder: press Write audit and read the "What this run does not show" part.

## Checklist

- [ ] Accept the final rules and confirm track, eligibility and required fields.
- [x] Real labeled evidence set: Open Images (`docs/dataset.md`).
- [ ] Optional: your own tray photos. Label them with `python -m blindspot_ci.cli label`, import, then run the live experiment on `-Dataset real`.
- [ ] Run `.\scripts\live_check.ps1`, then `.\scripts\live_experiment.ps1 -Dataset real`.
- [ ] Record the demo video.
- [ ] `python -m pytest` and `python -m blindspot_ci.cli demo` pass on a clean environment.
- [ ] `python scripts/package.py`, then check the file list: no `.env`, key, cache or private image.
- [ ] Describe it accurately: state the number of real photos, the threshold and which results are live.
- [ ] Replace the API key if the project folder was ever synced online or shared with a key in it.
- [ ] Submit through the Cerebral Valley portal before the deadline, then reopen the link to check.
