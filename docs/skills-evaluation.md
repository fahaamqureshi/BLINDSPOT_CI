# Skills evaluation

Reviewed November 3, 2026 from each repository's README, skill guidance, and license file. These sources were read as guidance only. No installer, plugin, package manager command, or source script from them was run.

| Repository | What it is | License | Verdict | Blindspot CI reason |
|---|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | A composable development method covering specification, planning, debugging, tests, and completion checks. | MIT | ADOPT-ADAPTED | Its root-cause-first debugging, red-green testing, and evidence before completion fit this Python evaluation harness. The useful parts are recorded as short workflow checks, not installed as a plugin. |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | A lifecycle skill set with measurement, review, web performance, and shipping stages. | MIT | ADOPT-ADAPTED | Its measure-first performance rule and ship checklist complement the existing Lighthouse and Craft Anything checks and give the hackathon handoff a small repeatable gate. |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | UI and UX design intelligence with design-system generation and platform guidance. | MIT | REFERENCE-ONLY | The UI worker is already using it. It helps visual work, but it does not improve the Python scoring, CI, or release workflow here. |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | Frontend art direction with browser inspection rules for pages and app screens. | MIT | REFERENCE-ONLY | The UI worker is already using it. Its browser and visual gates are outside this task's backend and evaluation scope. |
| [rebelytics/one-skill-to-rule-them-all](https://github.com/rebelytics/one-skill-to-rule-them-all) | A task-observer meta-skill that records session patterns and proposes future skill updates. | CC BY 4.0 | SKIP | Session-watching tooling adds a surveillance surface and does not help the Nov 4 deadline. The project needs focused checks, not a persistent observation log. |
| [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) | A structured browser agent that selects actions from observed controls and uses hosted model services. | MIT | SKIP | It needs Browser Use Cloud or TypeSafe and model API keys, with possible paid usage. Existing Lighthouse and Craft Anything browser checks cover the needed browser evidence without adding that dependency. |

The adopted practices are summarized in [agent-workflow.md](agent-workflow.md). The UI verdicts record the workers' current choices without changing their owned files.
