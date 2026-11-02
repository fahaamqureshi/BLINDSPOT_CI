# Metrics validation

Date: 2026-11-03. Python is the scorer. The supported task is single-target case success, not multi-object average precision.

## Definitions

Box IoU is intersection area divided by union area for half-open xyxy pixel boxes. Zero or reversed area gives zero. Best overlap against the one human box is compared at full precision with min_iou, default 0.35. Missing boxes on visible cases give FAIL_FALSE_NEGATIVE; boxes with insufficient overlap give FAIL_LOCALIZATION. On absent cases any box gives FAIL_FALSE_POSITIVE and no box gives PASS. Unknown visibility gives UNKNOWN and is excluded from scored denominators. Provider failure gives ERROR, not a miss.

Pass rate is passed/scored, with null for no scored cases. It is not detection precision or recall. A 95 percent Wilson interval accompanies it; no interval is returned for zero scored. Condition counts and underpowered flags expose small samples. Cluster-aware intervals and corrected slice tests have separate existing regression coverage.

Detection-level TP, FP, FN, precision, recall and F1 are not exported by this photo scorer. Image-level TN would mean an absent case with no detections. FNR would be FN/(FN+TP) and FPR FP/(FP+TN), only after specifying compatible image-level counts. Localization errors cannot be silently assigned to a confusion matrix. No invented confusion-matrix metrics were added.

There is one labeled object per case, so best-box selection cannot inflate recall by matching several labeled objects. Duplicate detections do not add passes, but surplus detections on positive cases are not penalized. Multi-object one-to-one matching and detection precision remain unsupported; do not present this harness as a multi-object detector benchmark. Confidence is recorded or null and does not establish calibration.

Mask IoU is separate and uses compatible human masks, not boxes pretending to be masks. Existing mask tests exercise a hole and no overlap. Real SAM mask alignment was not verified in this audit.

## Validation and corrections

Existing tests exercise perfect, partial, disjoint and degenerate boxes, threshold changes, visible misses, localization, absent negatives, unknown exclusion, Wilson arithmetic and small slices. New threshold regression: overlap 34996/100000 is less than 0.35 even though four-decimal rounding would reach the bar. The scorer now keeps full precision.

Comparisons now require unchanged available image hashes, labels, concept, dataset and min_iou. Missing provenance gives UNVERIFIED; mismatches and duplicate IDs are rejected. Different model versions are permitted because comparison is their purpose. Original reports record the model and planner prompt version; exact segmentation prompt is the case concept. Label provenance changes conservatively reject comparisons too.

New run reports record the entire configured inventory before planner selection. The gate checks it for missing, extra and duplicate cases, preventing a partial new run from reaching GO_CANDIDATE. Historical reports have no such inventory and cannot prove full-suite coverage. No fixture can produce release approval: mock provenance takes precedence and yields DEMO_ONLY.

Focused validation after fixes: 83 passed in 2.45s across scoring, runner, importer and gate. Full suite and final gate are in FINAL_VERDICT.md. Negative fixture workflow measured five tested, four scored, three passed, one deliberate low-light miss and one unknown. No real-model performance conclusion follows.
