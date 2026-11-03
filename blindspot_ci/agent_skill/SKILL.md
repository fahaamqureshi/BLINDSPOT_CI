---
name: blindspot-ci
description: Run BLINDSPOT CI vision-model evaluations, inspect failed cases and export reviewable evidence through its local CLI. Use for evaluating a detector on human-labeled cases, not for training or repairing the model.
---

# BLINDSPOT CI evaluation

Use the installed blindspot CLI, or python -m blindspot_ci.cli from its environment. Read command help if a flag is unavailable. Keep the user's chosen workspace and dataset. Do not overwrite labels or another run to make a demonstration succeed.

For first-use practice:

```text
blindspot init WORKSPACE
blindspot --workspace WORKSPACE doctor --mock --json
blindspot --workspace WORKSPACE experiment --mock --steps 5 --json
blindspot --workspace WORKSPACE serve --mock
```

For an existing evaluation, use doctor without --mock to check the selected configuration without inference. The --mock flag selects synthetic practice data. It is not a way to test a custom dataset against a real model.

A real provider run requires human references, the user's explicit live authorization and spending scope, and permitted credential configuration. Follow the project's rules. Do not read or display credential files. Do not enable live access just to complete a task. Labels must come from people or identified human annotations, never a model.

Use experiment --json for machine-readable results. Read an existing run with report --run RUN_ID --json. Preserve the source mode, planner, configured cases, tested subset, unknowns and errors. A selected subset is not a complete suite.

Export with card --run RUN_ID --out PATH. Inspect the policy through release-gate --run RUN_ID. Exit codes for that command are 0 GO_CANDIDATE, 1 NO_GO, 2 NEEDS_REVIEW, 3 DEMO_ONLY and 4 input error. A policy result is not a process crash or a safety certification.

Return the run identifier, actual outcome counts, missed or uncertain cases, the report path and what the user can investigate next. Clearly identify scripted practice, cached responses and fresh model calls. No result is evidence that the model was automatically fixed.
