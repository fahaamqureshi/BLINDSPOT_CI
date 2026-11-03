# Use BLINDSPOT CI from a coding agent

BLINDSPOT CI provides the same evaluation workflow through its browser, CLI and local HTTP API. A coding agent with terminal access can run the CLI, read JSON results and export evidence. The agent controls the workflow; SAM remains the supported vision provider and Python computes scores.

## Install the project skill

After installing BLINDSPOT CI, choose the project where you run your coding agent:

```bash
blindspot install-skill --target codex --project /path/to/project
blindspot install-skill --target claude --project /path/to/project
```

The commands copy the same instruction-only skill into the project's .agents/skills/blindspot-ci or .claude/skills/blindspot-ci directory. They preserve a different existing skill instead of overwriting it. No user-wide settings, credentials, MCP servers or extra agent-platform dependencies are changed.

Start or refresh a session in that project. Invoke $blindspot-ci in Codex or /blindspot-ci in Claude Code. Follow the client's workspace trust and skill-loading requirements. The skill expects access to the Python environment where BLINDSPOT CI is installed.

Example request:

```text
Use blindspot-ci to create a practice workspace, run five scripted tests,
inspect the failure and export the evidence card. Report the source mode,
tested coverage, unknowns and errors. Keep the result clearly labeled practice.
```

For your own cases, name the workspace, dataset and authorized provider configuration. Reference labels must come from people. A skill invocation does not itself authorize paid model calls or credential-file access.

## Machine-readable workflow

```bash
blindspot init /path/to/evaluation
blindspot --workspace /path/to/evaluation doctor --mock --json
blindspot --workspace /path/to/evaluation experiment --mock --steps 5 --json
blindspot --workspace /path/to/evaluation report --run RUN_ID --json
blindspot --workspace /path/to/evaluation card --run RUN_ID --out review.md
```

Successful experiment and report commands return the run identifier, source mode, planner, configured case identifiers, steps, outcomes and summary as JSON. Inspect the command exit code and error output as well. Reading a saved report makes no model call and includes saved reviewer extras. The --mock flag selects synthetic practice rather than your custom dataset.

Other terminal-capable harnesses can use the same commands without a skill. HTTP-capable agents can use the documented local API. This is not an MCP server, an arbitrary model backend or proof that every agent client supports the workflow.

## What was verified

Tests exercise installing both project layouts, preserving an edited skill, a machine-readable practice run, and reopening the same saved report. Installed-wheel verification repeats the skill installation and JSON workflow outside the source checkout. The skill file passes the skill-format validator.

The workflow is exercised through Codex's terminal tools. No separate authenticated Claude Code model session is claimed by those checks. Actual execution in another client depends on its environment, permissions and tool access.

## Sources

[OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills) describes Codex's repository skill discovery. [Claude Code skill documentation](https://code.claude.com/docs/en/skills) describes project skills and invocation. These sources informed the folder layouts; they do not establish unrestricted compatibility with all hosted or cloud sessions.
