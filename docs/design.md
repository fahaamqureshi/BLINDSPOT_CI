# Design

## Rules the code follows

1. A model can only be trusted within the conditions that were tested.
2. A blind spot is a mismatch between an expected object and a returned detection. It cannot be found
   from model output alone, so ground truth must be independent of the provider and the planner.
3. The search must stop: iteration limit, call limit and dollar budget are checked before each call.
4. Every real call has cost, latency and privacy risk, so budget is reserved before the call.
5. Anything that could affect safety goes to a human. The report says why.

## Modules

| File | Job |
| --- | --- |
| `agent.py` | the bounded loop and the review gate |
| `planner.py` | picks the next probe (heuristic, or Muse Spark with fallback) |
| `providers/mock.py` | deterministic answers from `fixtures/mock_responses.json` |
| `providers/meta.py` | Meta adapters: Responses API, retries, streaming, redacted errors |
| `providers/sam_output.py` | turns SAM 3.1 special-token text into detections |
| `evaluator.py` | per-label counts, precision, recall, weighted risk |
| `budget.py`, `cache.py`, `provenance.py` | spend guard, response cache, audit log |
| `media.py` | local image to data URL, with type and size checks |

## Experiment mode

| File | Job |
| --- | --- |
| `experiment/cases.py` | loads a manifest, validates labels and hashes, hides labels from the planner |
| `experiment/planners.py` | `MockToolPlanner` offline, `MuseToolPlanner` with strict function calling |
| `experiment/runner.py` | planner choice, cached SAM call, scoring, saved report, provenance |
| `experiment/scoring.py` | IoU and the six statuses. The only judge |
| `experiment/importer.py` | imports human-labeled photos with rotation, resize and hashing |
| `experiment/stress.py` | Muse Image variants: inherited box, `GENERATED` label, hash, private manifest |
| `experiment/reviews.py` | reviewer notes and the Wonder audit, saved beside a run, never touching scores |
| `providers/meta_extras.py` | Muse Image, Muse Voice Transcribe and Muse Wonder adapters |
| `web/index.html` | the app page: mode badge, trace, masks drawn on the photo |

Muse rules: one tool call per turn, a known function, a case id that is still untested. Anything else
stops the run safely and nothing is guessed. Each measured result returns to Muse in a `tool`
message with the matching call id.

## Planner prompt versions and replay

The Muse planner uses a versioned prompt registry, and each saved run records its planner prompt
version. The replay command runs a local test-ordering policy against statuses already saved in a run.
It does not evaluate the model or make network calls. UNKNOWN and ERROR outcomes are excluded. With
few cases this cannot separate skill from luck. A small p value is suggestive, a large one is
uninformative.

A SAM mask is local to its box and its SVG path uses mask pixel coordinates, so the page draws it
with a translate and a scale from mask size to box size. Boxes are half-open.

## Provider contract

`inspect(scenario, probe)` returns detections, raw text, usage, cost and a `parser_status`. A provider
must not read ground truth. `parser_status` is `structured` only for clean output or an empty
no-match. Anything else forces human review.

## Review gate

A run is `needs_human_review` for any of: blind spots, false alarms, unparsed output, a provider
error, or probes that did not run (iteration limit, planner stop, budget stop).

## Known limits

- Experiment scoring uses box overlap only. There is no mask-quality metric, and SAM returns no
  confidence scores.
- The mock policy is scripted, so its low-light miss is not a real finding.
- Muse tool calling goes through Chat Completions. It was verified live on 2026-10-31 with the
  synthetic drawings. The API accepts only `tool_choice: "auto"`, so a reply with no tool call stops
  the run safely.
- Generated variants inherit the source box on the assumption that Muse Image kept the tag in place.
  Nothing checks that automatically. A person must look at the yellow box in the trace.
- Muse Wonder writes free text from the saved results. It can be wrong, so the audit is labeled as
  model-written and a person reads it next to the scores.
- Voice notes accept WAV only (mono PCM, 16 kHz or 24 kHz). The page converts the recording itself.
- The synthetic dataset is labeled by program, not by a person. It is for development only.
- The probe-mode scenes are simulated. Only the sample-photo runs touched the real API.
- A recovery view is a separate photo. It does not show the agent moving a camera.
- Detections have no confidence score when Meta omits it.
- No reviewer sign-off step in the app.

## Possible next steps

Mask metrics, an information-gain planner, a sign-off endpoint, more real images, video.
