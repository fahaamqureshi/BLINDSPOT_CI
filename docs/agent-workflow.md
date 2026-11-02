# Agent workflow

## Reusable task prompt

Goal: state one concrete result and why it matters.

Scope files: list the files the agent may change. Do not change other files.

Completion checks: list exact commands and the expected result for each.

Stop conditions: list failures, missing inputs, or decisions that require the owner.

Ask the agent to report changed files, checks, open issues, branch, and commit SHA.

## Loop rules

1. Try a failing check at most three times. Diagnose the root cause before each retry.
2. Do not repeat a prompt unless new information or a changed input justifies it.
3. Keep one task on one branch.
4. Work on overlapping files sequentially. Do not make concurrent edits to them.
5. Stop and report the exact output when the same failure remains after three attempts.
6. Use mock or fixture mode for this project. Do not make live API calls.

## Debugging and fixes

Reproduce a failure before proposing a fix. Read the full error, inspect recent changes, trace the data through each boundary, and state one root-cause hypothesis. Make the smallest change that tests that hypothesis. If the same approach fails three times, stop and report the evidence.

The temporal report CI bug is the worked example. A broad hex-prefixed JSON filename pattern selected both the primary report and a `.temporal.json` report. The failure was ambiguous fixture selection, not bad report data. The fix narrowed the selection in [6eeb0b1](https://github.com/fahaamqureshi/BLINDSPOT_CI/commit/6eeb0b1f7c7cf9ceace7817c40d08f333ef14102) and [eb12eef](https://github.com/fahaamqureshi/BLINDSPOT_CI/commit/eb12eefabf45fe742d56e3605071863bed5bf4ce). Reproduce, trace, and then fix the source of the ambiguity.

For a feature or bug fix, use red-green TDD:

- Write one small test for the desired behavior.
- Run it and confirm the expected failure.
- Write the smallest implementation that passes.
- Run the focused test and the full relevant suite.
- Refactor only while the suite stays green.

## Verification before completion

Run a fresh gate against the final tree. Record the exact output from `python scripts/check.py`, including `Summary: PASS`, and include relevant test and CI output. Do not claim a fix from an old run, an inspection without output, or a mock result that says nothing about model performance. A failed gate is a blocker to report, not a result to explain away.

## Pre-submission checklist

- [ ] Gate from `main`, after fetching the latest `origin/main`.
- [ ] Rebase before a fast-forward merge if `origin/main` moved.
- [ ] `python scripts/check.py` prints `Summary: PASS`.
- [ ] GitHub CI is green for the final `main` commit, or its status is reported as a blocker.
- [ ] The README mock quickstart is accurate for a fresh checkout.
- [ ] No secret or API key is present in the tracked package.
- [ ] A demo script is present and the README or demo notes point to it.
- [ ] Review the diff for scope and report changed files, checks, open issues, branch, and commit SHA.

## Agent fallback order

Use agents in this order when the current agent is out of quota: claude-code, codex,
opencode-v2. Record the fallback and any reduced verification in the final report.
