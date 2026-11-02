# Evaluation protocol

This protocol states exactly how a case becomes a score, so two readers given the same saved run reach the same numbers. It is implemented in `blindspot_ci/experiment/scoring.py` and `blindspot_ci/experiment/release_gate.py`. No model takes part in scoring. If this file and the code disagree, the code wins and this file must be fixed.

## Labels before the test

- A person labels each case before any model run: visibility (visible, absent or unknown), and for visible cases one box as integer pixels [x1, y1, x2, y2], half-open, inside the upright photo. Only visible cases may hold a box. This is validated on load in `blindspot_ci/experiment/cases.py`, including a hash check that the photo has not changed since labeling.
- Each label carries provenance: annotator name, time, and reviewer when a second person checked it. Labels copied from SAM or Muse output are forbidden by design; the importer and labeler take boxes only from a person.
- Labels stay hidden during the test. The planner and the browser see the public case (id, title, condition, concept, image size, note) and never the box or visibility. Ground truth is attached to a step only after scoring.

## Matching rules

- One case asks for one concept in one photo. The model answer is the set of boxes it returned for that concept.
- Visible case: compute IoU (intersection over union) between the human box and every returned box. The best (largest) IoU is the case IoU. Best IoU at or above the bar passes; below the bar fails as FAIL_LOCALIZATION (the model found something, in the wrong place). No returned box fails as FAIL_FALSE_NEGATIVE with IoU 0.0.
- The bar is 0.35 by default (BLINDSPOT_MIN_IOU) and is recorded in every run and shown in every report. Changing the bar changes the run; the offline sweep exists to show sensitivity instead of hiding the choice.
- A box with zero or negative area scores IoU 0.0. Confidence is recorded when the API gives one and is null otherwise; it never affects matching, because SAM often returns no score.
- Masks do not affect the photo score. Mask quality (Jaccard J against a human mask) is a separate offline measurement for datasets that have human masks, currently DAVIS via `scripts/eval_masks.py`. It is reported beside, never instead of, the box result.

## Unknown, occluded and absent handling

- Unknown visibility: the status is UNKNOWN, scoreable is false, IoU is null, and the reason states the case is not determinable from the image. It counts in tested and in the unscored share, never in scored, passed or failed. Use unknown when a person truly cannot tell; it is the honest bucket, not a way to hide a hard case, because the gate fails a run whose unscored share exceeds 5 percent.
- Occluded is a condition tag, not a visibility. The person draws the box on what they can judge (for MOT20, on the full person including hidden parts, which the notes flag as a convention that can lower overlap). An occluded visible case is scored by the normal matching rules. There is no partial credit and no lowered bar for occlusion.
- Absent target: any returned box fails as FAIL_FALSE_POSITIVE; no returned box passes. IoU is null in both sub-cases because there is no human box to overlap. Absent cases are required by the default gate policy, so a set with no negatives cannot reach GO_CANDIDATE.
- Provider or parser failure: the step is ERROR, scoreable false, and the run records the reason. An unparseable provider answer is never scored as a miss. In long video, frames whose answers never arrived (truncated stream) are likewise errors, not misses.

## Aggregation and intervals

- Summary counts always show tested, scored, passed, failed, unknown and errors, overall and per condition. A rate is passed divided by scored. Quote counts with their interval, never a bare percentage.
- Interval for a proportion: 95 percent Wilson score interval (Brown, Cai and DasGupta 2001), used because the Wald interval misbehaves at the small counts this tool works with. Implemented once in scoring and reused by the gate, the sweep and the card.
- Underpowered flag: a slice with fewer than 5 scored cases is reported as underpowered and never described as a rate. The gate needs far more: 29 scored cases per required condition (the failure-free count needed to claim a failure rate under 10 percent at 95 percent confidence, from the rule of three in `blindspot_ci/experiment/power.py`) plus a Wilson lower bound at or above the 0.90 pass bar.
- Clip-aware intervals: for DAVIS and MOT20 runs, scored frames are grouped by clip or by sequence and target, and whole groups are bootstrapped (2000 resamples, fixed seed 20260427) in `blindspot_ci/experiment/cluster_ci.py`. When a condition has enough repeated groups, the gate shows both intervals and judges the lower bound by the lower of the two. With too few groups it prints by clip not available rather than a fake narrow interval. Photo datasets have no groups and are unchanged.
- Slice comparisons: each condition is compared with all other scored cases by a two-sided Fisher exact test with Holm correction in `blindspot_ci/experiment/slice_tests.py`. A slice under 5 scored cases is never called worse. These p values treat photos or frames as independent and are about chance only, not effect size.
- IoU sweep: saved box pairs are rescored at 0.25, 0.35, 0.50 and 0.75 in `blindspot_ci/experiment/iou_sweep.py`. Steps without both boxes keep their saved outcome and are counted as not rescored, with the reason stated.
- Regression between runs: paired scored cases only, exact sign test, in `blindspot_ci/experiment/regression.py`. Planner quality: exact hypergeometric comparison against random order in `blindspot_ci/experiment/baseline.py`, which needs every case scored once.

## Gate decision rules (summary)

Full rules live in `docs/release-gate.md`. Order matters: mock, fixture, synthetic, generated or corrupted evidence gives DEMO_ONLY and nothing else is evaluated. Otherwise a required condition with at least 10 scored cases and an observed pass rate under 0.90 gives NO_GO. Anything else that fails a check (sample size, Wilson or clip lower bound, unscored share over 5 percent, second annotator coverage under 30 percent, kappa under 0.60, non-live mode, training overlap not proven clean) gives NEEDS_REVIEW. GO_CANDIDATE only when every check passes. A person still decides; GO_CANDIDATE is not a safety approval.

## Limitations (state these with any quoted result)

- Small samples: headline slices hold 8 to 30 scored cases. Intervals are wide and one run is one pass, not a failure rate for the world.
- Single labeler: most labels come from one person or one source dataset. A wrong box becomes a wrong score. The second annotator check exists in the gate and currently fails for lack of an agreement file.
- Public sets may overlap training: DAVIS is marked likely seen (UNVERIFIED, from SAM paper summaries) and COCO unknown. Only photos the owner took after the model release can pass the overlap check today, and none exist yet. This alone blocks GO_CANDIDATE.
- Correlation: frames from one clip or one tracked person look alike. Counting 112 frames as 112 independent tests overstates certainty; read DAVIS as about 14 clips and MOT20 as 16 people in one sequence.
- Label conventions differ: MOT20 boxes include hidden body parts while SAM boxes cover visible parts, so occluded long-video scores mix convention with error. COCO absent means no annotation of that class, weaker than a verified negative.
- Threshold and prompt sensitivity: results hold for IoU 0.35, the recorded prompts, model versions and run date. The sweep shows threshold movement; a prompt change needs a new run.
- GO_CANDIDATE has never been reached. No result here is a benchmark ranking or a safety approval, and mock or fixture numbers are never model performance.
