# Fresh terminal-to-web demonstration

Date: 2026-11-04. The owner authorized a six-photo live SAM 3.1 and Muse Spark evaluation, including private credential loading by the app. No credential was displayed, logged or copied into the delivery.

## The user journey

The three-minute film starts after installation. It shows actual workspace initialization, offline setup checks, fresh human-labeled input data, import, a browser evaluation, failure inspection, a reviewer note, export and coding-agent integration. The question it answers is practical: what does a developer provide, what does the app measure, and what can the developer do with the result?

The use case is inspecting roadside objects. Six previously unused COCO val2017 photographs were selected before inference: three traffic lights, two stop signs and a fire hydrant. Three targets are small and three are larger references. The labels are original COCO human annotations. They are not new independent labels or model-generated references. Source-listed photo licenses are CC BY 2.0; the delivery preserves source and license links.

## Actual recorded outcomes

| Report | Observation | Model requests |
| --- | --- | --- |
| Agent run 3b3343b61a0f427d | Five of six cases tested; four passes, one missed distant stop sign; no unknowns or execution errors | Six Muse Spark turns and five SAM requests; LIVE_META |
| Complete report b33d8b6f4ce447e6 | Six of six cases tested; five passes and the same miss; NEEDS_REVIEW | Five predictions reused from cache and one new SAM request; scripted completion; MIXED_CACHED_AND_LIVE_META |

The study made twelve logical model requests in total. The application-reported estimated cost was USD 0.033, which is an estimate rather than a billing statement. The agent run took 57.6 seconds; the complete report took 5.2 seconds. The film shortens waiting time and identifies the recorded evaluation.

The missed case is fresh_road_261888. SAM returned no target box for the distant stop sign. The visible expected box comes from the original human annotation. An enlarged crop is an editorial detail, not a new inference input. A typed reviewer note asks for more small-sign cases and investigation before release. No model was automatically repaired.

## Terminal and integration evidence

Actual commands execute from the existing validated checkout and write a new workspace. Their captured output is displayed in a browser terminal panel and recorded. Desktop controls blocked launching PowerShell for native capture. Automatic approval review also rejected the combined fresh-clone recording/startup command with the stated reason blocked by policy. That script remained stopped. The film starts after installation and does not claim to show a new clone or dependency installation.

The bundled skill installs into Codex and Claude Code project directories. The JSON report command reads the saved complete report without inference. Skill installation, JSON execution and reopening the same report pass local tests and installed-wheel checks. No separate authenticated Claude Code model session is represented as recorded footage. See [agent integration](AGENT_INTEGRATION.md) for supported invocation and client boundaries.

## Delivery and limits

The local delivery folder is C:/Users/faham/Downloads/BLINDSPOT_CI_TERMINAL_TO_WEB_DEMO_2026-11-04. It contains the film, captions, narration, source credits, original input references, model-input hashes, both reports, exported cards, raw recordings, a chapter player and editable composition.

Live access for this recording is stopped after the authorized study. The local review server runs in mock mode and can reopen the saved real reports without new model calls. The source application remains configurable for separately authorized live operation.

This is a small selected challenge study. Training overlap is unknown, independent second-labeler review is absent, and the sample does not cover all release-policy conditions. No benchmark, general accuracy, production approval or safety certification is claimed. Four photo creators were resolved through Flickr public metadata; two original photo records could not be retrieved. The film shows four creator-attributed photo examples while retaining all six cases and their outcomes in the evidence pack. Retain source links and review attribution before public distribution. No public upload or contest submission was performed.
