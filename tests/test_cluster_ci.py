import json
from pathlib import Path

import pytest

from blindspot_ci.experiment import release_gate as rg
from blindspot_ci.experiment.cluster_ci import cluster_interval, group_key
from blindspot_ci.experiment.scoring import wilson_interval

COCO_RENDER_BEFORE_CLUSTER = """Release Gate decision: NO_GO

CHECKS
  PASS pass rate absent: 29/30, Wilson 95% [0.833, 0.994], bar 0.9
  PASS sample size absent: 30 scored, need 29
  FAIL Wilson lower bound absent: 0.833, bar 0.9
  FAIL pass rate low_light: 6/10, Wilson 95% [0.313, 0.832], bar 0.9
  FAIL sample size low_light: 10 scored, need 29
  FAIL Wilson lower bound low_light: 0.313, bar 0.9
  PASS pass rate normal: 24/24, Wilson 95% [0.862, 1.0], bar 0.9
  FAIL sample size normal: 24 scored, need 29
  FAIL Wilson lower bound normal: 0.862, bar 0.9
  FAIL pass rate small_object: 19/24, Wilson 95% [0.595, 0.908], bar 0.9
  FAIL sample size small_object: 24 scored, need 29
  FAIL Wilson lower bound small_object: 0.595, bar 0.9
  PASS pass rate truncated: 14/14, Wilson 95% [0.785, 1.0], bar 0.9
  FAIL sample size truncated: 14 scored, need 29
  FAIL Wilson lower bound truncated: 0.785, bar 0.9
  PASS unscored share: 0/132 = 0.000, max 0.05
  FAIL second annotator coverage: no agreement file given
  FAIL annotator kappa: no agreement file given
  PASS live evidence: mode LIVE_META
  FAIL training overlap: coco-val2017: unknown if seen in SAM training

FAILING CONDITIONS
  low_light: 6/10, Wilson 95% [0.313, 0.832], pass rate 0.600 below 0.9
  small_object: 19/24, Wilson 95% [0.595, 0.908], pass rate 0.792 below 0.9

RECOMMENDED NEXT EXPERIMENTS
  add a second annotator on at least 30 percent of cases and run compare-labels
  add photos you took yourself after the model release, or document that the model never saw this set
  collect 11 more normal photos (all must pass to meet the bar)
  collect 21 more truncated photos (all must pass to meet the bar)
  collect 23 more absent photos (all must pass to meet the bar)
  fix the 4 failing low_light cases, then re-run on fresh photos
  fix the 5 failing small_object cases, then re-run on fresh photos

TRACEABILITY
  dataset_id: coco-val2017
  dataset_type: HUMAN_LABELED_OPEN_DATA_COCO_VAL2017
  distinct_image_hashes: 132
  mode: LIVE_META
  policy_version: 1
  run_id: a165cd6773cd433a
  run_sha256: 756b31c8b3af3449349e88e29762f3ee3c26a0df19b1445571ee56d455ab9994

POLICY USED
  max_unscored_share: 0.05
  min_cases_per_condition: 29
  min_judged_cases: 10
  min_kappa: 0.6
  min_pass_rate: 0.9
  min_second_annotator_share: 0.3
  policy_version: "1"
  require_no_training_overlap: true
  required_conditions: ["normal", "low_light", "small_object", "truncated", "absent"]

Human review is mandatory. GO_CANDIDATE is not a deployment approval or safety certification."""


def _step(case_id, condition, status="PASS", group=None):
    case = {"id": case_id, "condition": condition}
    if group is not None:
        case["group"] = group
    return {"case": case, "outcome": {"status": status}}


def _run(steps):
    return {"id": "a" * 16, "mode": "LIVE_META",
            "dataset": {"id": "owner-fresh", "type": "HUMAN_LABELED_OWN_PHOTOS"},
            "steps": steps}


def _run_with_dataset(steps, dataset_id):
    run = _run(steps)
    run["dataset"] = {"id": dataset_id, "type": "HUMAN_LABELED_VIDEO"}
    return run


def test_group_keys_use_explicit_value_and_known_video_ids():
    assert group_key(_run([]), _step("photo_1", "normal", group="clip-a")) == "clip-a"
    assert group_key({"dataset": {"id": "davis-2017-frames"}},
                     _step("dv_bear_f012", "normal")) == "bear"
    assert group_key({"dataset": {"id": "mot20-long"}},
                     _step("MOT20-03-7-695", "normal")) == "MOT20-03-7"
    assert group_key({"dataset": {"id": "coco-val2017"}},
                     _step("cc_normal_01", "normal")) is None


def test_singleton_groups_have_no_cluster_interval():
    groups = {f"clip-{i}": [i % 2 == 0] for i in range(8)}
    assert cluster_interval(groups) is None


def test_repeated_groups_are_deterministic_and_wider_than_wilson():
    groups = {f"clip-{i}": [i < 7] * 8 for i in range(14)}
    first = cluster_interval(groups)
    second = cluster_interval(groups)
    wilson = wilson_interval(56, 112)
    assert first == second and first is not None
    assert first[1] - first[0] > wilson[1] - wilson[0] + 0.10


def test_all_pass_groups_have_zero_width_and_are_not_used_by_gate():
    groups = {f"clip-{i}": [True, True] for i in range(5)}
    assert cluster_interval(groups) == [1.0, 1.0]
    steps = [_step(f"MOT20-03-{i}-{frame}", "small_object", "PASS")
             for i in range(5) for frame in (1, 2)]
    report = rg.evaluate(_run_with_dataset(steps, "mot20-long"), rg.load_policy(None), None)
    assert "cluster_ci95" not in report["conditions"]["small_object"]
    assert "by clip: n/a (too few clips to estimate)" in next(
        c["detail"] for c in report["checks"] if c["name"] == "pass rate small_object")


def test_fewer_than_five_groups_are_not_used_by_gate():
    groups = {f"clip-{i}": [i % 2 == 0, i % 2 == 0] for i in range(4)}
    assert cluster_interval(groups) is not None
    steps = [_step(f"MOT20-03-{i}-{frame}", "small_object", "PASS" if i % 2 == 0 else "FAIL_LOCALIZATION")
             for i in range(4) for frame in (1, 2)]
    report = rg.evaluate(_run_with_dataset(steps, "mot20-long"), rg.load_policy(None), None)
    check = next(c for c in report["checks"] if c["name"] == "Wilson lower bound small_object")
    assert "by clip: n/a (too few clips to estimate)" in check["detail"]


def test_gate_uses_the_lower_cluster_bound():
    steps = [_step(f"MOT20-03-{target}-{frame}", "small_object",
                   "PASS" if target < 5 else "FAIL_LOCALIZATION")
             for target in range(1, 6) for frame in range(8)]
    report = rg.evaluate(_run_with_dataset(steps, "mot20-long"), rg.load_policy(None), None)
    condition = report["conditions"]["small_object"]
    assert condition["cluster_ci95"] is not None
    check = next(c for c in report["checks"] if c["name"] == "Wilson lower bound small_object")
    assert check["status"] == "FAIL"
    assert "by clip" in check["detail"] and "lower" in check["detail"]


def test_run_without_groups_has_old_render_shape_and_no_cluster_text():
    run = _run([_step("photo_1", "normal"), _step("photo_2", "normal", "FAIL_LOCALIZATION")])
    before = rg.render(rg.evaluate(run, rg.load_policy(None), None))
    after = rg.render(rg.evaluate(json.loads(json.dumps(run)), rg.load_policy(None), None))
    assert before == after
    assert "by clip" not in after


@pytest.mark.skipif(not Path("C:/Users/faham/Downloads/BLINDSPOT_CI/artifacts/runs/a165cd6773cd433a.json").is_file(),
                    reason="saved COCO run is outside this checkout")
def test_saved_coco_render_has_no_cluster_interval():
    path = Path("C:/Users/faham/Downloads/BLINDSPOT_CI/artifacts/runs")
    rendered = rg.render(rg.evaluate_file(path, "a165cd6773cd433a", rg.load_policy(None)))
    assert rendered == COCO_RENDER_BEFORE_CLUSTER
