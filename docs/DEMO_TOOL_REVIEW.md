# Demo-tool review and three-minute revision

Reviewed on 2026-11-04 for BLINDSPOT CI, on Windows, with English narration and a three-minute judging format.

## Tool comparison

| Tool | Documented approach | Fit for this film |
| --- | --- | --- |
| [Aidemo](https://github.com/tandryukha/aidemo) | Real browser replay, a declarative storyboard, narration, captions and focus zoom; local voice is supported | Best conceptual fit for authentic app walkthroughs and repeatable capture |
| [DemoDay](https://github.com/mrieck/demoday-claude-plugin) | Narrated app capture with transitions and optional presenter; documented requirements include macOS and paid generation through fal.ai | Its explainer structure is useful; its capture and generation dependencies do not fit this Windows offline edit |
| [Agentic Product Demo](https://github.com/Alexwtlf/agentic-product-demo) | React and Remotion compositions, product styling, planned motion beats and visual frame review | Useful for restrained diagrams and editorial callouts; reconstructed UI should not replace evidence of the real product |
| [Brag](https://github.com/latent-spaces/brag) | Short launch-video storytelling and rendering through Hyperframes | Useful for a concise opening and delivery structure; the requested complete walkthrough needs more explanation than a short trailer |

This is a task-specific comparison, not a measured ranking of video engines. The repositories were inspected as reference material. Project rules prohibit executing downloaded code, so no new repository engine was installed or run. The revision adapts their browser-replay, story, composition and review ideas using the existing agent-browser installation, local rendering code and FFmpeg. No Aidemo, DemoDay, Remotion or Hyperframes engine validation is claimed.

## Revised story

The new film opens with the user problem and a plain explanation of the product. It then shows the current landing page, an actual scripted practice check, human-reference inputs, the bounded planner loop, agent coverage and the separate complete suite. Three failures explain the value of independent scoring. Day and night video observations, image stress, voice transcription and report explanation follow. The ending returns to reviewer notes and an exportable evidence package.

The public-camera freshness experiment is omitted from this cut to keep the main evaluation story clear. All five configured model responsibilities remain represented. Optional capabilities are not presented as calls made during every check.

## Evidence boundaries

Practice is labeled scripted and does not measure SAM. Other model scenes replay saved actual responses. The agent selected eight passing cases from twenty configured cases. The separate complete suite found three failures outside that selection. The film does not say the agent discovered those failures.

Video frame records are observations without an accuracy score. Generated variants require human reference review. Voice demonstrates transcription, without claiming microphone capture. Muse Wonder cannot change Python scores. The release decision remains human review.

Current interface captures use a mock-only local server. Recorded real reports are opened from local replay copies; the source model reports remain unchanged. Narration uses the installed Microsoft Mark speech synthesizer. No new model call, cloud voice service or spending is required.

## Delivery

The revision is delivered locally under C:/Users/faham/Downloads/BLINDSPOT_CI_SUBMISSION_DEMO_2026-11-04. The primary film is BLINDSPOT-CI-submission-demo.mp4. The package includes captions, transcript, chapters, source credits, evidence references, editable composition files and validation results. See [demo-video history](DEMO_VIDEO.md) for earlier cuts.

This edit prepares a submission asset. It does not submit an entry or establish compliance with a particular contest's unpublished requirements. Third-party media retains its own terms, documented in the accompanying credits.
