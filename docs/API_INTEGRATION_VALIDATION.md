# API integration validation

## Current evidence scope

Saved live execution is now available in FULL_LIVE_MODEL_TEST.md for all five configured roles, including actual Muse Spark tool calls and SAM observations. REAL_WORLD_VIDEO_DEMO.md records two further fresh SAM video requests, 929 returned frames and independently verified human-reference scoring. No paid API call was made in this readiness pass. The earlier mock-only statement below describes that earlier audit, not the project's present evidence inventory.

Transport implementations were not replaced. This pass corrects the reusable video importer's API index mapping and validates it with intercepted transport. It does not claim the original tray scenario has real photographs, that model performance improved, or that saved evidence is a new inference call. Historical long-video headline statistics need frame-mapping review.

Reviewed 2026-11-03. Live SAM inference verified in this audit: NO. Live Muse tool calling verified in this audit: NO. Offline fixture and intercepted HTTP contract tests: PASS. Repository instructions require mock-only execution, so credentials were not inspected and no real smoke request was attempted. Historical saved runs are archival evidence, not a new live validation.

## Official contract review

The implementation uses https://api.meta.ai/v1, bearer authentication, sam-3.1 on Responses, a user message containing one input_text concept and an input_image URL or data URL, and streaming completion handling. These shapes agree with the reviewed official request examples. The transport implements finite timeouts, bounded retries and refusal/error handling. Offline tests cover malformed envelopes, terminal failures, parser behavior and segmentation coordinates. This validates local handling, not account access or service compatibility end to end.

SAM parser uses the installed meta-sam-parser package. Official documentation defines half-open parsed boxes, missing confidence as absent rather than zero, and raster decoding of genuine masks. The UI uses boxes; live pixel alignment remains unverified.

Muse planner uses muse-spark-1.3, Chat Completions function declarations, tool_choice auto, JSON argument decoding, assistant tool-call history and tool messages with matching call IDs. Server validation limits allowable tools and untested case IDs. Arrays and null now stop safely. Offline nine-tool loop tests cover budgets, cancellation, malformed arguments, prohibited scoring edits and requests for additional evidence. The browser route uses the simpler case planner. Neither proves live intelligence or improvement over random selection.

## Sources

- [Overview](https://dev.meta.ai/docs/overview)
- [SAM cookbook](https://dev.meta.ai/docs/cookbook/sam-api-basics)
- [SAM client libraries](https://dev.meta.ai/docs/sam/client-libraries)
- [SAM request and coordinates](https://dev.meta.ai/docs/sam/segmenting)
- [Muse tool calling](https://dev.meta.ai/docs/cookbook/tool-function-calling)

No documentation example code was downloaded or executed. Documentation access does not authorize paid requests. Required next evidence is an owner-authorized live smoke test with permitted data, followed by a sanitized response and overlay review in a separate session.
