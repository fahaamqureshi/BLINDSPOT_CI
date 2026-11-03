# Fresh three-minute judge demo

Date: 2026-11-03. This preparation follows an explicit new user authorization for a finite live test without a dollar ceiling. The scoped live session retained a 100-request maximum and disabled automatic retries. Normal application defaults were not changed. Credential loading occurred privately inside the authorized helper; no key was displayed or copied into the demo folder.

The complete folder is C:/Users/faham/Downloads/BLINDSPOT_JUDGE_DEMO_2026-11-03. Open http://127.0.0.1:8050/judge-demo/ while its recording server runs. If needed, double-click Start-Recording-Demo.cmd in that folder. The page replays actual saved results; playback makes no new API call. The exact 180-second storyboard, narration and input map are in THREE_MINUTE_GUIDE.md inside the folder.

## Selected data

Twenty human-reference images were selected before inference from Open Images: four normal, two low-light, four small-object, four truncated, two general helmet occlusion controls and four human-verified negative controls. Concepts are nine traffic-light, six fire-hydrant, three stop-sign and two helmet cases. The set excludes 102 prior downloaded Open Images IDs. Candidates that appeared to be artwork or edited scenes were excluded before inference. Fresh means new to this project, not newly captured or proven absent from model training.

The existing source human annotations provide the reference boxes and verified negatives. They were not created by a model. Input hashes, source IDs and the pre-inference inventory were retained. The official [Open Images description](https://storage.googleapis.com/openimages/web/factsfigures_v7.html) lists annotations as CC BY 4.0 and images as CC BY 2.0, while requiring individual image-rights review. The current Flickr source pages were unreachable from this environment, so the folder retains that limitation rather than certifying current rights. Every photo has its source, author, listed license and hash.

Two fresh camera-style Pexels sources were downloaded: [daytime intersection by Richard L](https://www.pexels.com/video/busy-city-intersection-with-traffic-and-pedestrians-33049294/) and [rainy-night crossing by George Morina](https://www.pexels.com/video/street-in-a-city-on-a-rainy-night-5687586/). Each model input is fifteen seconds, 960 by 540, 24 fps. Original downloads and six extracted stills are included. These are prerecorded stock clips under the [Pexels License](https://www.pexels.com/license/), not a live camera feed or CC0 media. They have no human reference boxes and are not accuracy-scored.

Voice inputs are a 5.855-second human LibriSpeech excerpt and a separately labeled 9.913-second Windows-synthesized QA note. The human sample is 1272-128104-0000 from [LibriSpeech / OpenSLR 12](https://www.openslr.org/12), listed under CC BY 4.0, downloaded through Hugging Face's public sample-data endpoint without running dataset code. Its original reference text and attribution are retained. The human clip is an audiobook transcription control, not an annotation about a photographed object. Hardware microphone capture remains untested.

## Actual live results

The complete fixed image run is 3d453bfa36d44771. All twenty cases received fresh SAM requests: seventeen passed, three failed, no unknowns and no execution errors. The release decision is NEEDS_REVIEW. Failures are fresh_absent_02, a false positive; fresh_normal_04, a localization disagreement at IoU 0.1072; and fresh_small_object_03, a false negative. Each condition remains a small sample. These are observed case outcomes, not general accuracy or industrial safety claims.

The separate browser agent run is 8fe8e41fd99d4b43. Actual Muse Spark selected eight tests and SAM inspected each. All eight passed. The run stopped at its configured eight-step limit. None of the three fixed-suite failures was in the agent's selected sample. The recording must say the fixed full suite found those failures, not that Muse discovered them. This directly illustrates why an agent-selected subset cannot substitute for release coverage.

Both video requests completed at the transport. The daytime request returned all 360 frame records. The night response returned 186 records, frames 90 through 275. The initial helper expected complete coverage and flagged this; the raw output was preserved, no automatic retry occurred, and the viewer now exposes unreturned intervals without assigning an accuracy score. Night billed-frame usage was not retained by that helper, so no exact billing claim is made for it. Six extracted stills were separately inspected without reference scoring.

Muse Image returned a darker derivative of fresh_normal_05. SAM inspected the derivative, but it was not accuracy-scored because inherited reference geometry needs human review. Muse Voice returned transcripts for both fresh audio inputs through the actual app voice endpoint. Muse Wonder returned an audit of the complete fixed run and reviewer notes. It identified the three failures and did not alter Python's scores. All five configured model roles executed actual requests.

The finite session made 49 model requests. A conservative estimate from returned token usage, thirty-five image requests, video input frames, one image edit and audio duration is USD 0.40699495. It uses all 720 video input frames because night billed usage was not retained. It is not an invoice. The [official pricing page](https://dev.meta.ai/docs/pricing-rate-limits) was checked. Raw usage, model outputs, notes, hashes and cost calculation remain local in 05_results.

## Recording route

1. Fresh inputs: explain source human labels and fixed selection before inference.
2. Agent exploration: show the eight actual planner choices and measured outcomes.
3. Full audit: inspect the three genuine failures and the complete twenty-case app report.
4. Camera-style video: play both actual prediction overlays and disclose the night frame gaps and missing references.
5. Image, voice, audit: compare the actual generated derivative, play the human audio control, show the transcript and actual Wonder explanation.
6. Export and credits: download the evaluation card and point to sources and limitations.

The full recording guide assigns exact time ranges summing to 180 seconds. It is based on the owner's requested duration; private portal requirements remain unverified. New live testing has a separate explicit launcher and can produce different results or latency. The recording launcher starts a local read-only inference viewer, disables dotenv and live calls, and blocks accidental new experiment execution.

## Validation and deliverables

The selected image manifest was validated through the real importer and loader. Actual app reports and their cards reopened. Browser checks covered the six-section recording page, failure image loading, generated-image comparison, daylight playback, night seeking, audio readiness and mobile overflow. Screenshots and request evidence are local. The final required source gate runs in mock mode; its exact output is retained with the preparation artifacts and reported in the final response.

Only this guide is a new tracked deliverable. Media, copied workspace, generated output, downloaded annotations, local helpers and raw results remain outside the shared source package. The folder includes an input contact sheet, numbered media folders, normalized app dataset, actual saved runs, credits, per-file hashes, recording launcher and three-minute guide. A portable ZIP of the prepared folder is also local. No push, deployment, public media upload or hackathon submission occurred.

Open limitations: individual Flickr rights could not be independently rechecked; third-party publication terms need the owner's final review; public training overlap is unknown; there is no second annotator; the video has no reference boxes; the generated variant needs reference review; the microphone and a live webcam feed were not tested. The product is an evaluation harness, not a benchmark or safety approval.
