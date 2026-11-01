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

The training overlap check asks whether the model may have already seen the test set. It passes only
for a dataset listed as not_seen, such as photos you took yourself after the model release. Anything
else fails it, and a fail can lower GO_CANDIDATE to NEEDS_REVIEW but never changes NO_GO or DEMO_ONLY.
The table is TRAINING_OVERLAP in release_gate.py. DAVIS is marked likely seen. COCO, Open Images and
MOT20 are marked unknown, as is any unlisted dataset. This overlap is unverified: it comes from
summaries of the SAM 2 paper (https://arxiv.org/abs/2408.00714) and the SAM 3 paper
(https://arxiv.org/abs/2511.16719), which states no contamination analysis. Read both papers
before quoting it. Set require_no_training_overlap to false to skip the check (status NA).

## Policy

DEFAULT_POLICY has policy_version "1". A JSON file overrides keys; unknown keys are rejected. The
policy used is printed with every result. Keys: required_conditions (normal, low_light,
small_object, truncated, absent), min_judged_cases 10, min_pass_rate 0.90, min_cases_per_condition
29 (power.cases_needed(0.10)), max_unscored_share 0.05, min_second_annotator_share 0.30, min_kappa 0.60,
require_no_training_overlap true (the only boolean key).

Second annotator coverage is cases_compared in the agreement file divided by distinct cases in the run.

## Output

The decision, one line per check, failing conditions with passed over total and Wilson interval,
recommended next experiments, and traceability: run id, dataset id and type, mode, sha256 of the run
file, policy version and the count of distinct image hashes. Labels, file contents and keys are never
printed. Output is sorted and deterministic.

## Offline IoU sweep

Use `python -m blindspot_ci.cli iou-sweep --run <id>` to rescore saved visible box pairs at
0.25, 0.35, 0.50 and 0.75. Add `--bars` followed by one or more bars to choose them. Each
condition shows passes over scored and a Wilson 95 percent interval. Steps without both stored
boxes are reported as not rescored. The command also flags a condition when its pass or fail
status against the policy pass bar changes between bars. It makes no model calls and exits 0.

## Offline slice tests

Use `python -m blindspot_ci.cli slice-tests --run <id>` to compare each condition with all other
scored cases. The table gives the pass rate difference, a two-sided Fisher exact p value, and the
Holm adjusted p value. A slice with fewer than five scored cases is underpowered and is never called
worse. The p values are about chance only. Frames or photos are treated as independent observations.

## Clip-aware intervals

For saved DAVIS and MOT20 runs, the gate groups scored frames by clip or sequence and target, then
bootstraps whole groups with a fixed seed. When a condition has repeated groups, its checks show a
Wilson interval and a by-clip interval. The lower-bound check uses the lower of the two lower bounds.
Photo datasets have no groups, so their output and decision stay unchanged.

## In the web app and the card

Open a saved run in `/app` to see the Release gate panel below the results table.
It shows the decision, every check, failing conditions, and recommended next experiments.
Download the evaluation card to find the same decision and checks in its Release gate section.
Human review is mandatory for every decision, and mock, synthetic or generated evidence is DEMO_ONLY.
