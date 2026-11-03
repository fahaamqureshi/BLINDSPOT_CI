# Complete live model and application test

Date: 2026-11-03. Branch: codex/full-live-model-test. Baseline: 175bfe9fe838102f538a30c0711495a8e87c1d00.

The user replaced the earlier USD 0.10 allowance with an explicit USD 30 total authorization for this broader live test. Private credential loading was authorized. No key was displayed, committed or written to results. Test-specific limits allowed the full 132-case audit and all configured model roles; normal application safeguards were not removed globally. Live calls were disabled when testing finished.

## Actual model results

| Model | Executed task | Outcome |
| --- | --- | --- |
| SAM 3.1 | 143 image calls across human-labeled COCO, synthetic practice, six new video frames and one generated variant; two ten-second video calls | Responses completed; inference success is separate from scored accuracy |
| Muse Spark 1.3 | Five actual planning turns in the browser workflow, four executed cases and a finish decision | Valid model tool calling, with observation-dependent reasons |
| Muse Image 1.0 | Darker variant of a real public-domain input | Returned a decodable image; SAM then inspected it; no inherited accuracy claim |
| Muse Voice Transcribe 1.0 | Eleven-second generated test WAV, submitted through the app's voice-note endpoint | Transcript saved beside the run; one inserted background word against a 24-word reference |
| Muse Wonder 1.0 | Browser audit action on the actual live practice run and its reviewer note | Audit text returned and persisted; it did not change scores |

All five configured roles answered successfully. This is not a claim that every possible input, microphone, deployment or product feature has been tested exhaustively. Muse Voice is transcription, not a speech-generation service. Its test audio was explicitly Windows-synthesized test speech, not a human recording or a fabricated model voice output.

## Independent real-image audit

New run: 7b72db162422464c. All 132 configured COCO cases were tested with fresh SAM calls, using the existing source human annotations and a fixed scripted planner. Muse did not select which cases counted. Runtime: 328 seconds. Calls: 132. Estimated image cost: USD 0.33.

| Condition | Passed / scored | 95 percent Wilson interval |
| --- | --- | --- |
| Normal | 24 / 24 | 0.862 to 1.000 |
| Low light | 6 / 10 | 0.313 to 0.832 |
| Small object | 19 / 24 | 0.595 to 0.908 |
| Truncated | 14 / 14 | 0.785 to 1.000 |
| Absent | 29 / 30 | 0.833 to 0.994 |
| Other object | 18 / 20 | 0.699 to 0.972 |
| Look-alike scene | 8 / 10 | 0.490 to 0.943 |
| Overall | 118 / 132 | 0.830 to 0.936 |

Fourteen scored failures, zero unknowns and zero execution errors. Release gate: NO_GO. This is a real new inference result, not the earlier committed example replayed. Comparing against saved example a165cd6773cd433a passed the input-hash, labels, concept, dataset and threshold compatibility checks. That example passed 119 of 132; the new run passed 118. One case regressed, cc_other_object_04. The exact paired comparison gave p = 1.0 and WARN, not a significant overall deterioration claim.

Public COCO training overlap, single-source labels, negative-label conventions, small condition samples and box-only single-target scoring remain limitations. This result is not certification or a new benchmark ranking.

## Browser agent workflow

Run 43b2ab75827c4de3 used actual Muse Spark and SAM calls on the five-case synthetic practice inventory. Muse tested four cases and finished early. Normal, alternate view and low light produced false negatives; the absent control passed. After the baseline miss Muse selected the alternate view, then a negative control, then low light. These reasons and tool-call IDs were recorded, not invented afterward. The untested obstructed case remains untested, not a pass.

The practice run's gate is DEMO_ONLY because its images and labels are synthetic. It must not be quoted as real-photo performance. It is separate from the full 132-case human-labeled audit. The browser's case-selection planner was tested; the separate nine-tool Python agent loop was not misrepresented as this browser workflow.

The run received an actual Muse Voice transcript through POST voice and an actual Muse Wonder audit through the browser. Reports were exported. Twelve concurrent reads succeeded. Invalid test limits, malformed JSON, corrupt WAV, unknown note cases and foreign-origin mutations were rejected without additional paid calls. Original scores were unchanged after voice and audit output.

The service was restarted in mock mode using the same saved-run directory. Summary, voice notes and audit text reopened unchanged. Both the live practice report and fixed audit remained accessible. New paid calls are disabled in the saved-results viewer.

## New open-media checks

Two public-domain sources from the [Xiph collection](https://media.xiph.org/video/derf/) were used:

- [Johnny video](https://media.xiph.org/video/derf/webm/Johnny_1280x720_60.webm)
- [Kristen and Sara video](https://media.xiph.org/video/derf/webm/KristenAndSara_1280x720_60.webm)

Each was converted to a ten-second, 640 by 360 MP4 at 24 fps, capped at 240 frames. Each request returned 240 frame records and reported 240 processed frames. Six actual still frames at 0, 4 and 8 seconds were inspected separately. A Muse Image variant and a subsequent SAM inspection completed too.

No model-created reference labels were introduced. These new-media tasks establish live inference and playback, not detection accuracy. Generated image edits require human review before labels could be reused. The old public sources do not prove training independence. No Kaggle account or restricted download was required.

## Cost evidence

There were 153 successful API requests in this test session: 132 in the fixed audit, 11 in the application workflow and 10 in the additional-media tests. Automatic retries were disabled. Successful usage at published prices is estimated at USD 0.6095329, approximately USD 0.61. It is not an independently checked invoice and excludes the separate earlier USD 0.10 smoke-test session.

The calculation includes 143 images, 480 video frames, one generated image, eleven billed audio seconds and returned Spark/Wonder input/output/cached token usage. Reasoning tokens included in completion usage were not dropped from the cost estimate. The existing app's flat per-call estimates are not the official bill; for example Wonder's actual token-priced estimate here exceeded its simple USD 0.03 reservation. The temporary live-test guard reserved USD 0.50 per application call instead. The experiment call limit was raised explicitly for the full fixed audit.

Prices were checked against [official Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits). Muse's protocol was checked against [official tool-calling documentation](https://dev.meta.ai/docs/cookbook/tool-function-calling).

## Product corrections

The technical-details view now exposes the actual per-step planner reason, tool-call ID, prediction source and Python outcome. It also shows tested versus configured case count. Future experiment reports explicitly record whether they stopped because the suite completed, a planner finished, a limit was reached, or an execution/planner error occurred. Legacy reports honestly say when a stop reason was not recorded.

Two remaining misleading technical labels were corrected: negative-case counts say Passed, and the minimum condition sample is described as the threshold for a NO_GO decision, not as a point before an individual miss counts.

Changed source files: blindspot_ci/web/index.html, blindspot_ci/experiment/runner.py and tests/test_experiment_runner.py. This document is the remaining tracked change. Test media, generated content, raw responses, ledger, transcripts, reports and screenshots remain under ignored artifacts/full-live-test.

## Verification and review

Focused runner tests: 23 passed in 0.72s. Final required gate, executed in mock mode:

```text
PASS  ruff
PASS  pytest
PASS  docs style
PASS  attribution
PASS  secrets

Summary: PASS
```

Review the combined local report at http://127.0.0.1:8021/full-live-report.html. Saved app runs are at http://127.0.0.1:8030/app?run=7b72db162422464c and http://127.0.0.1:8030/app?run=43b2ab75827c4de3. Viewing them makes no model call. Both report videos and the generated WAV reached browser readyState 4. Planner trace, voice, audit and all-model screenshots are retained locally.

Open limitations: hardware microphone capture was not exercised; there is no browser image-upload or project CRUD feature; public authentication, atomic production spending controls and hosted deployment remain unverified. Independent human labels are still needed for the new videos. No push, publication or hackathon submission occurred. The model evidence remains NO_GO, even though the tested application flows executed successfully.
