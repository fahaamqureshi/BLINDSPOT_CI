# Judge overview

[Product](../README.md) | [Architecture](ARCHITECTURE.md) | [Walkthrough](GETTING_STARTED.md)

## The problem

A vision model can look convincing on a few examples and still miss objects in low light, with small targets or under occlusion. A polished prediction overlay alone does not tell an engineer what was tested, what was missed or whether the evidence supports a release decision.

## The solution

BLINDSPOT CI connects test selection, vision inference, independent Python scoring and reviewable evidence. Muse Spark can choose the next test through validated function calls. SAM 3.1 produces predictions. Human references determine the expected outcome. The application preserves failures, unknowns, condition coverage and a deterministic policy decision.

The useful output is an inspectable evaluation report, not a claim that an agent made a model safe. Optional Muse Image, Muse Voice Transcribe and Muse Wonder capabilities support stress variants, spoken review input and report explanation.

## Three-minute presentation

| Time | Show | Explain |
| --- | --- | --- |
| 0:00 to 0:20 | Home and workspace | The problem: plausible predictions can hide failures |
| 0:20 to 0:55 | Practice drawings, five tests, Run check | Clearly state that this first workflow uses scripted fixtures |
| 0:55 to 1:30 | Test evidence and the low-light miss | Compare the reference and prediction; distinguish the unknown case |
| 1:30 to 2:05 | A saved real report | Identify it as recorded evidence; show a failure and its source |
| 2:05 to 2:35 | Architecture and selection limitations | Muse selects, SAM predicts, Python scores; coverage still matters |
| 2:35 to 3:00 | Reviewer note and exported report | A person receives the evidence and makes the decision |

Prepare the server using the mock-only quick start. Rehearse the transitions and select the saved report before recording. The bundled reports support a replay without new model calls. If a source photograph is unavailable, show its explicit missing-photo notice rather than presenting an empty overlay as a photograph.

The [demo script](DEMO_SCRIPT.md) contains the detailed practice route. The [fresh dataset guide](JUDGE_DEMO_GUIDE.md) and [video case study](REAL_WORLD_VIDEO_DEMO.md) describe additional local evidence whose raw media is not bundled. A recording that uses those assets requires an independent check of their terms.

## What the evidence establishes

| Evidence | Supported statement | Limitation |
| --- | --- | --- |
| Five-case practice run | The software exposes a deliberate miss, an unknown and an exportable report | Synthetic data and scripted answers do not measure a model |
| COCO saved run | A fixed-order 132-case study recorded failures, including low-light and small-object cases | Limited study, unknown training overlap, no agent selection |
| DAVIS saved run | A fixed-order study recorded 112 frames from 14 clips | Correlated frames do not constitute 112 independent scenarios |
| Fresh local study | Eight agent-selected cases passed while the separate twenty-case suite found three failures | A bounded agent sample missed those failures; local assets are not bundled |

Do not combine these studies into a single accuracy number. Labels, scoring rules, sample sizes and model provenance matter. No recorded run established deployment or safety approval.

## What is ready to show

- A local landing page and responsive evaluation workspace.
- A deterministic practice flow requiring no model credential.
- Inspectable references, predictions, outcomes and provenance.
- Saved real reports, reviewer notes and Markdown or JSON export.
- A bounded agent architecture and documented model responsibilities.
- Automated mock, packaging and installed-wheel checks.

Browser photo upload, account management and continuous camera monitoring are not implemented product flows. Do not demonstrate them as completed features.

## Submission preparation

Use the current [readiness checklist](SUBMISSION_READINESS.md) and [demo-video notes](DEMO_VIDEO.md). Confirm contest-specific requirements, repository access for judges, video availability and third-party asset permissions before submitting. A GitHub source update is separate from a hosted deployment or a completed contest submission.

The repository's source license does not grant rights to third-party photographs, video, audio or music. Keep secrets, private datasets and locally downloaded media out of the submission unless their sharing terms have been confirmed.
