# Release Gate

The Release Gate answers one question: does the saved evidence for a vision model support advancing
toward deployment, and what must be fixed first. It reads one saved run report and makes no model
calls and no spend. It is conservative on purpose.

Human review is mandatory. GO_CANDIDATE is not a deployment approval or safety certification.

## Command

```powershell
python -m blindspot_ci.cli release-gate --run <id> [--policy policy.json] [--agreement agreement.json] [--format text|markdown|json] [--out FILE]
```

The agreement file is the JSON printed by `compare-labels`. Run reports are read from
`artifacts/runs`, or from the folder in BLINDSPOT_RUNS_DIR.

## Decisions and exit codes

| Decision | Exit | Meaning |
|---|---|---|
| GO_CANDIDATE | 0 | Every check passes. A person still decides. |
| NO_GO | 1 | A required condition has enough scored cases and its observed pass rate is below the bar. |
| NEEDS_REVIEW | 2 | No NO_GO, but evidence is thin, uncertain, unreviewed, or not live. |
| DEMO_ONLY | 3 | Mock, fixture, synthetic, generated or corrupted evidence. Nothing else is evaluated. |

Exit 4 means the run, policy or agreement file could not be read.

Mock, fixture, synthetic, generated and corrupted evidence can never produce any decision other
than DEMO_ONLY, however good the numbers look.

## Checks

Only scored statuses count (PASS and the FAIL statuses). UNKNOWN and ERROR are not scored. Families
such as low_light_s3 count under low_light. For each required condition the gate checks:

- pass rate, where NO_GO needs at least min_judged_cases scored cases below min_pass_rate
- sample size of at least min_cases_per_condition scored cases
- Wilson 95 percent lower bound at or above min_pass_rate

Across the run it also checks the unscored share, second annotator coverage, kappa, and that the mode
is LIVE_META, CACHE_LIVE_META or MIXED_CACHED_AND_LIVE_META.

## Policy

DEFAULT_POLICY has policy_version "1". A JSON file overrides keys; unknown keys are rejected. The
policy used is printed with every result. Keys: required_conditions (normal, low_light,
small_object, truncated, absent), min_judged_cases 10, min_pass_rate 0.90, min_cases_per_condition
29 (power.cases_needed(0.10)), max_unscored_share 0.05, min_second_annotator_share 0.30, min_kappa 0.60.

Second annotator coverage is cases_compared in the agreement file divided by distinct cases in the run.

## Output

The decision, one line per check, failing conditions with passed over total and Wilson interval,
recommended next experiments, and traceability: run id, dataset id and type, mode, sha256 of the run
file, policy version and the count of distinct image hashes. Labels, file contents and keys are never
printed. Output is sorted and deterministic.
