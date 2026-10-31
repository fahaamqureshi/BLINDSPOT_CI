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

## Agent fallback order

Use agents in this order when the current agent is out of quota: claude-code, codex,
opencode-v2. Record the fallback and any reduced verification in the final report.
