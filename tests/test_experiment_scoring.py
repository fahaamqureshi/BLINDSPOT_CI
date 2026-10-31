import pytest

from blindspot_ci.experiment import scoring
from blindspot_ci.experiment.cases import InspectionCase


def make_case(visibility="visible", box=(10, 10, 110, 110), case_id="c1"):
    return InspectionCase(case_id, "Case", "samples/normal.png", "normal", "red safety tag", visibility,
                          box if visibility == "visible" else None)


def test_iou_identical_disjoint_and_degenerate():
    assert scoring.box_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert scoring.box_iou((0, 0, 10, 10), (10, 0, 20, 10)) == 0.0
    assert scoring.box_iou((5, 5, 5, 9), (0, 0, 10, 10)) == 0.0
    assert scoring.box_iou((0, 0, 10, 10), (0, 0, 10, 5)) == pytest.approx(0.5)


def test_visible_pass_false_negative_and_localization():
    case = make_case()
    assert scoring.score_case(case, [(12, 12, 108, 108)]).status == scoring.PASS
    miss = scoring.score_case(case, [])
    assert (miss.status, miss.iou) == (scoring.FALSE_NEGATIVE, 0.0)
    far = scoring.score_case(case, [(200, 200, 300, 300)])
    assert far.status == scoring.LOCALIZATION and far.scoreable


def test_best_box_wins_when_several_are_returned():
    outcome = scoring.score_case(make_case(), [(300, 300, 400, 400), (10, 10, 110, 110)])
    assert outcome.status == scoring.PASS and outcome.iou == 1.0


def test_absent_cases():
    case = make_case("absent")
    assert scoring.score_case(case, []).status == scoring.PASS
    assert scoring.score_case(case, [(0, 0, 5, 5)]).status == scoring.FALSE_POSITIVE


def test_unknown_is_never_scored():
    outcome = scoring.score_case(make_case("unknown"), [(0, 0, 5, 5)])
    assert outcome.status == scoring.UNKNOWN and not outcome.scoreable


def test_threshold_is_respected():
    case = make_case()
    half = [(10, 10, 110, 60)]
    assert scoring.score_case(case, half, min_iou=0.4).status == scoring.PASS
    assert scoring.score_case(case, half, min_iou=0.6).status == scoring.LOCALIZATION


def test_summary_counts_and_denominators():
    cases = {"a": make_case(case_id="a"), "b": make_case("absent", case_id="b"),
             "c": make_case("unknown", case_id="c")}
    outcomes = [scoring.score_case(cases["a"], []), scoring.score_case(cases["b"], []),
                scoring.score_case(cases["c"], [])]
    summary = scoring.summarize(outcomes, {"a": "low_light", "b": "absent", "c": "occlusion"}, 0.35)
    assert summary["note"] == scoring.NOTE
    assert (summary["tested"], summary["scored"], summary["passed"], summary["failed"]) == (3, 2, 1, 1)
    assert summary["unknown"] == 1 and summary["errors"] == 0 and summary["pass_rate"] == 0.5
    assert summary["by_condition"]["low_light"]["failed"] == 1
    assert summary["by_condition"]["occlusion"]["scored"] == 0
    assert summary["by_condition"]["occlusion"]["pass_rate"] is None
    assert summary["failures"] == ["a"]
    assert "not a safety approval" in summary["note"]


def test_wilson_interval_matches_known_values_and_edges():
    from blindspot_ci.experiment.scoring import wilson_interval

    lo, hi = wilson_interval(3, 8)
    assert (lo, hi) == (0.137, 0.694)  # derived by hand: center 0.4155, half-width 0.2781
    assert wilson_interval(0, 10)[0] == 0.0 and wilson_interval(10, 10)[1] == 1.0
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(0, 5)
    assert 0.0 == low and 0.4 < high < 0.5  # zero failures in 5 is not proof of zero risk


def test_summary_marks_small_slices_underpowered():
    from blindspot_ci.experiment.scoring import ERROR, PASS, CaseOutcome, summarize

    outcomes = [CaseOutcome(f"c{i}", PASS, True, 0.9, "") for i in range(4)] + [CaseOutcome("e", ERROR, False, None, "")]
    summary = summarize(outcomes, {o.case_id: "normal" for o in outcomes}, 0.35)
    assert summary["underpowered"] is True and summary["pass_ci95"][1] == 1.0
    assert summary["by_condition"]["normal"]["scored"] == 4


def test_noise_on_a_large_photo_is_bounded_and_keeps_its_size():
    import random
    import time

    from PIL import Image

    from blindspot_ci.experiment.corruptions import noise

    big = Image.new("RGB", (3000, 2000), (120, 120, 120))
    start = time.monotonic()
    out = noise(big, 3, random.Random(1))
    assert out.size == big.size and time.monotonic() - start < 8


def test_mask_rasterize_and_iou_with_a_hole():
    from PIL import Image, ImageDraw

    from blindspot_ci.experiment.mask_eval import human_mask_from_labels, mask_iou, rasterize

    outer = "M0 0L10 0L10 10L0 10Z"
    hole = "M3 3L7 3L7 7L3 7Z"
    mask = {"bounds_xyxy": [5, 5, 15, 15], "width": 10, "height": 10, "svg_path": outer + hole}
    got = rasterize(mask, (20, 20))
    labels = Image.new("L", (20, 20), 0)
    draw = ImageDraw.Draw(labels)
    draw.polygon([(5, 5), (15, 5), (15, 15), (5, 15)], fill=1)
    draw.polygon([(8, 8), (12, 8), (12, 12), (8, 12)], fill=0)
    human = human_mask_from_labels(labels)
    assert mask_iou(got, human) > 0.9
    assert mask_iou(got, Image.new("1", (20, 20), 0)) == 0.0


def test_sample_size_arithmetic():
    from blindspot_ci.experiment.power import cases_needed, upper_bound_no_failures

    assert cases_needed(0.05) == 59 and cases_needed(0.01) == 299 and cases_needed(0.001) == 2995
    assert 0.029 < upper_bound_no_failures(100) < 0.030


def test_two_annotators_agreement():
    from blindspot_ci.experiment.agreement import cohen_kappa, compare_labels

    def label(case_id, vis, box, who):
        return {"id": case_id, "ground_truth": {"visibility": vis, "bbox": box}, "label_provenance": {"annotator": who}}

    first = {"cases": [label("a", "visible", [0, 0, 10, 10], "P1"), label("b", "absent", None, "P1"),
                       label("c", "visible", [0, 0, 10, 10], "P1")]}
    second = {"cases": [label("a", "visible", [0, 0, 10, 11], "P2"), label("b", "visible", [1, 1, 5, 5], "P2"),
                        label("c", "visible", [50, 50, 60, 60], "P2")]}
    report = compare_labels(first, second)
    assert report["cases_compared"] == 3 and round(report["visibility_agreement"], 2) == 0.67
    assert {d["case"] for d in report["to_discuss"]} == {"b", "c"}
    assert cohen_kappa(["x", "y"], ["x", "y"]) == 1.0


def test_regression_gate_pairs_cases_and_uses_an_exact_test():
    from blindspot_ci.experiment.regression import compare_runs, sign_test_p

    def run(statuses):
        return {"steps": [{"case": {"id": f"c{i}"}, "outcome": {"status": s}} for i, s in enumerate(statuses)]}

    good = run(["PASS"] * 12)
    bad = run(["FAIL_LOCALIZATION"] * 8 + ["PASS"] * 4)
    report = compare_runs(good, bad)
    assert len(report["regressions"]) == 8 and report["verdict"].startswith("FAIL")
    assert compare_runs(good, good)["verdict"].startswith("OK")
    assert compare_runs(run(["PASS"] * 5), run(["FAIL_LOCALIZATION"] + ["PASS"] * 4))["verdict"].startswith("WARN")
    assert sign_test_p(0, 0) == 1.0 and sign_test_p(8, 0) < 0.01
