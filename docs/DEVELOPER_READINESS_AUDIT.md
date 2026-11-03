# Developer-readiness audit

Date: 2026-11-04. Scope: local developer setup, backend input handling, configuration, imports, storage, CLI and installed-package verification. Live inference and paid services are excluded.

## Findings and fixes

| Finding | Impact | Fix and evidence |
| --- | --- | --- |
| Import paths were tied to the checkout or installed package | A wheel user had no supported separate data workspace | init and --workspace supply public fixtures and user-owned storage; subprocess and installed-wheel checks exercise it outside the checkout |
| Setup required several environment variables and had no offline diagnostic command | New developers could not easily distinguish configuration, data and storage problems | doctor provides human or JSON output without a provider call; serve --mock selects a safe practice route |
| Unknown provider or planner strings could fall back to scripted behavior | A typo could select a different workflow than intended | Configuration rejects unsupported choices explicitly |
| Non-finite scoring thresholds were accepted | A NaN threshold could bypass an overlap comparison | Settings and score_case reject non-finite or out-of-range thresholds |
| Missing default datasets bypassed normal API validation | An ordinary setup error could become HTTP 500 | Experiment requests validate the selected dataset before constructing the runner |
| Malformed manifest shapes reached unchecked field access | Invalid user data could produce inconsistent errors | Shape and field checks return controlled input errors |
| Live diagnostic helpers did not consistently consult the live-enabled setting | Direct CLI helpers could request remote services while the setting was false | Shared helper authorization checks refuse those commands before any request |
| Credential appeared in the default Settings representation | Logging or debugging the object could expose it | Credential field is excluded from repr; diagnostics no longer print credential structure |
| A later import conflict was detected after earlier images had been written | A rejected batch could leave an unexpected partial import | All target conflicts and encoded size limits are checked before image writes; existing-import regressions verify preservation |
| Relative image paths depended on the caller's current directory | A labels file could fail when invoked from another folder | Relative source paths resolve against the labels file |
| Source hashes were calculated after output writes | A forced in-place re-encode could record the stored image as the original source | Source hashes are captured before writing targets; a JPEG regression checks both hashes |
| Negative experiment limits saved an empty run | A command-line input mistake could create misleading output | Runner rejects non-positive step limits before writing a report |
| Port selection required environment configuration | Common --port usage failed or invalid port values produced poor errors | serve accepts validated --host and --port options |

## Tool assessment

[shadcn/improve](https://github.com/shadcn/improve) documents a prioritized audit and implementation-planning workflow. It is not itself a guarantee that code is repaired. Its evidence, impact and verification approach informed this audit.

[OpenHands](https://github.com/OpenHands/OpenHands) and [Kilo Code](https://github.com/Kilo-Org/kilocode) are coding-agent platforms. Adding another platform is unnecessary to repair the concrete issues above. Their repositories were checked as reference material, not installed or executed. The pasted search summary is not treated as proof of any tool's capabilities.

[DeepSeek's prototype](https://github.com/deepseek-ai/dsh-superagent-prototype) describes itself as research code rather than a production-ready product. [Project Graveyard](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/project-graveyard) examines abandoned-project history; it is not a general backend repair engine. [Scope Creep Detector](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills/scope-creep-detector) checks diffs against their intended scope. Keeping this change focused on local developer readiness follows that useful principle without installing additional tooling.

The work uses the existing local Python tools and regression suite. Downloaded executable code, live provider access and credentials were not needed.

## Verification and boundaries

Regression coverage includes invalid settings, HTTP error handling, scoring thresholds, disabled live helpers, import preservation and a fresh workspace from another directory. Installed-wheel verification creates a workspace and runs practice outside the checkout. The mock audit covers HTTP, caching, export, concurrent reads and restart. The final completion gate checks lint, tests, documentation style, attribution and secret patterns.

This is a local developer tool, not an authenticated public service. Browser uploads, accounts, general project management and an always-on camera product remain outside the implemented flow. A provider adapter is an extension interface, not a promise of compatibility with every model. Recorded media rights and contest submission requirements are separate from backend readiness.

Permission checks are a best-effort local diagnostic, not a guarantee that later disk writes will succeed. Import preflight is not a multi-file database transaction. Existing dependency deprecation warnings should be handled as a future compatibility update, not hidden by suppressing them. Mock outcomes are software checks and do not establish model performance or safety approval.
