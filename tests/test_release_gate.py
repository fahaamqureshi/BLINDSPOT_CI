import json

import pytest

from blindspot_ci import cli
from blindspot_ci.experiment import release_gate as rg

REAL = {"id": "coco-val2017", "type": "HUMAN_LABELED_OPEN_DATA_COCO_VAL2017"}
NEED = rg.DEFAULT_POLICY["min_cases_per_condition"]
GOOD_AGREEMENT = {"cases_compared": 999, "visibility_kappa": 0.8}


def _steps(plan):
    """plan maps a condition to (passed, failed, unknown)."""
    out = []
    for cond, (ok, bad, unk) in plan.items():
        for status, n in (("PASS", ok), ("FAIL_FALSE_NEGATIVE", bad), ("UNKNOWN", unk)):
            for _ in range(n):
                i = len(out)
                out.append({"case": {"id": f"c{i}", "condition": cond}, "outcome": {"status": status},
                            "image_sha256": f"h{i}"})
    return out


def _run(plan, mode="LIVE_META", dataset=REAL, run_id="a" * 16):
    return {"id": run_id, "mode": mode, "dataset": dataset, "steps": _steps(plan)}


STRONG = {c: (60, 0, 0) for c in rg.DEFAULT_POLICY["required_conditions"]}


FRESH = {"id": "owner-fresh", "type": "HUMAN_LABELED_OWN_PHOTOS"}


@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.setitem(rg.TRAINING_OVERLAP, "owner-fresh", rg.NOT_SEEN)


def _decide(run, agreement=GOOD_AGREEMENT, policy=None):
    return rg.evaluate(run, policy or rg.load_policy(None), agreement)


def test_go_candidate_and_human_review_sentence(fresh):
    report = _decide(_run(STRONG, dataset=FRESH))
    assert report["decision"] == rg.GO_CANDIDATE
    text = rg.render(report)
    assert "Human review is mandatory. GO_CANDIDATE is not a deployment approval or safety certification." in text
    assert "Human review is mandatory" in rg.render(_decide(_run(STRONG, dataset=FRESH), None), "markdown")


def test_partial_or_duplicate_fixed_suite_cannot_pass(fresh):
    run = _run(STRONG, dataset=FRESH)
    run["configured_case_ids"] = [s["case"]["id"] for s in run["steps"]] + ["omitted"]
    assert _decide(run)["decision"] == rg.NEEDS_REVIEW
    run["configured_case_ids"].remove("omitted")
    assert _decide(run)["decision"] == rg.GO_CANDIDATE
    run["steps"].append(run["steps"][0])
    assert _decide(run)["decision"] == rg.NEEDS_REVIEW


def test_six_of_ten_low_light_is_no_go():
    plan = {**STRONG, "low_light": (6, 4, 0)}
    report = _decide(_run(plan))
    assert report["decision"] == rg.NO_GO
    assert report["conditions"]["low_light"]["passed"] == 6
    assert any(f.startswith("low_light: 6/10") for f in report["failing"])


def test_low_light_family_counts_and_few_failures_is_not_no_go():
    plan = {**STRONG, "low_light": (0, 0, 0), "low_light_s3": (6, 4, 0)}
    assert _decide(_run(plan))["decision"] == rg.NO_GO
    thin = {**STRONG, "low_light": (5, 4, 0)}  # 9 scored, below min_judged_cases
    assert _decide(_run(thin))["decision"] == rg.NEEDS_REVIEW


def test_thin_condition_needs_review_with_concrete_fix():
    report = _decide(_run({**STRONG, "truncated": (NEED - 1, 0, 0)}))
    assert report["decision"] == rg.NEEDS_REVIEW
    assert any(n.startswith("collect") and "truncated" in n for n in report["next_experiments"])


def test_unknown_is_excluded_from_counts_but_counts_as_unscored():
    run = _run({**STRONG, "normal": (60, 0, 30)})
    report = _decide(run)
    assert report["conditions"]["normal"]["scored"] == 60
    assert report["decision"] == rg.NEEDS_REVIEW
    assert any("unscored share" in c["name"] and c["status"] == "FAIL" for c in report["checks"])


def test_missing_or_weak_agreement_needs_review():
    assert _decide(_run(STRONG), None)["decision"] == rg.NEEDS_REVIEW
    assert _decide(_run(STRONG), {"cases_compared": 10, "visibility_kappa": 0.9})["decision"] == rg.NEEDS_REVIEW
    assert _decide(_run(STRONG), {"cases_compared": 999, "visibility_kappa": 0.2})["decision"] == rg.NEEDS_REVIEW
    fixes = _decide(_run(STRONG), None)["next_experiments"]
    assert "add a second annotator on at least 30 percent of cases and run compare-labels" in fixes


def test_not_live_mode_needs_review():
    assert _decide(_run(STRONG, mode="NOT_A_MODE"))["decision"] == rg.NEEDS_REVIEW


@pytest.mark.parametrize("mode", ["MOCK_FIXTURE", "CACHE_MOCK_FIXTURE", "MOCK_THING"])
def test_mock_run_never_exceeds_demo_only(mode):
    report = _decide(_run({**STRONG, "low_light": (1, 9, 0)}, mode=mode))
    assert report["decision"] == rg.DEMO_ONLY and report["checks"] == []


@pytest.mark.parametrize("dataset", [
    {"id": "synthetic-maintenance-tray-v0", "type": "SYNTHETIC_DEVELOPMENT_FIXTURES_NOT_VALIDATION_DATA"},
    {"id": "generated-from-x", "type": "GENERATED_STRESS_VARIANTS_NOT_REAL_PHOTOS"},
    {"id": "corrupted-from-x", "type": "MEASURED_CORRUPTIONS_OF_LABELED_PHOTOS"},
    {"id": "mystery", "type": "UNSPECIFIED"},
])
def test_non_real_dataset_is_demo_only_even_when_live_and_perfect(dataset):
    assert _decide(_run(STRONG, dataset=dataset))["decision"] == rg.DEMO_ONLY


def test_policy_overrides_and_unknown_key_rejected(tmp_path):
    good = tmp_path / "p.json"
    good.write_text(json.dumps({"min_pass_rate": 0.5}))
    assert rg.load_policy(good)["min_pass_rate"] == 0.5
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"min_pass_rat": 0.5}))
    with pytest.raises(ValueError, match="min_pass_rat"):
        rg.load_policy(bad)


def test_determinism_and_traceability():
    run = _run({**STRONG, "low_light": (6, 4, 0)})
    a, b = rg.render(rg.evaluate(run, rg.load_policy(None), None, "ab")), rg.render(rg.evaluate(run, rg.load_policy(None), None, "ab"))
    assert a == b and "run_sha256: ab" in a and "distinct_image_hashes:" in a and "policy_version: 1" in a
    assert json.loads(rg.render(rg.evaluate(run, rg.load_policy(None)), "json"))["decision"] == rg.NO_GO


@pytest.mark.parametrize("plan,expected", [(STRONG, 0), ({**STRONG, "low_light": (6, 4, 0)}, 1),
                                           ({**STRONG, "truncated": (5, 0, 0)}, 2)])
def test_cli_exit_codes(tmp_path, monkeypatch, capsys, plan, expected, fresh):
    (tmp_path / f"{'b' * 16}.json").write_text(json.dumps(_run(plan, dataset=FRESH, run_id="b" * 16)))
    agreement = tmp_path / "agree.json"
    agreement.write_text(json.dumps(GOOD_AGREEMENT))
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    out = tmp_path / "out.txt"
    monkeypatch.setattr("sys.argv", ["cli", "release-gate", "--run", "b" * 16, "--agreement", str(agreement),
                                     "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == expected
    assert out.read_text().strip() == capsys.readouterr().out.strip()


def test_cli_demo_only_and_bad_input_exit_codes(tmp_path, monkeypatch):
    (tmp_path / f"{'c' * 16}.json").write_text(json.dumps(_run(STRONG, mode="MOCK_FIXTURE", run_id="c" * 16)))
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path))
    for run, code in (("c" * 16, 3), ("d" * 16, 4)):
        monkeypatch.setattr("sys.argv", ["cli", "release-gate", "--run", run])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == code


def _overlap(report):
    return next(c for c in report["checks"] if c["name"] == "training overlap")


def test_likely_seen_dataset_needs_review_even_if_all_else_passes():
    davis = {"id": "davis-2017-frames", "type": "HUMAN_LABELED_OPEN_VIDEO_FRAMES"}
    report = _decide(_run(STRONG, dataset=davis))
    assert report["decision"] == rg.NEEDS_REVIEW
    check = _overlap(report)
    assert check["status"] == "FAIL" and "likely seen in SAM training" in check["detail"]
    assert "after the model release" in check["fix"]


def test_not_seen_dataset_is_go_candidate(fresh):
    report = _decide(_run(STRONG, dataset=FRESH))
    assert report["decision"] == rg.GO_CANDIDATE and _overlap(report)["status"] == "PASS"


def test_unlisted_dataset_needs_review():
    other = {"id": "never-listed", "type": "HUMAN_LABELED_OPEN_DATA"}
    report = _decide(_run(STRONG, dataset=other))
    assert report["decision"] == rg.NEEDS_REVIEW and "unknown" in _overlap(report)["detail"]


def test_overlap_never_changes_no_go_or_demo_only():
    davis = {"id": "davis-2017-frames", "type": "HUMAN_LABELED_OPEN_VIDEO_FRAMES"}
    assert _decide(_run({**STRONG, "low_light": (6, 4, 0)}, dataset=davis))["decision"] == rg.NO_GO
    assert _decide(_run(STRONG, mode="MOCK_FIXTURE", dataset=davis))["decision"] == rg.DEMO_ONLY


def test_policy_key_false_is_na_and_go_candidate(fresh):
    policy = {**rg.load_policy(None), "require_no_training_overlap": False}
    report = _decide(_run(STRONG), policy=policy)
    assert report["decision"] == rg.GO_CANDIDATE and _overlap(report)["status"] == "NA"


def test_boolean_accepted_only_for_overlap_key(tmp_path):
    ok, bad = tmp_path / "ok.json", tmp_path / "bad.json"
    ok.write_text(json.dumps({"require_no_training_overlap": False}))
    assert rg.load_policy(ok)["require_no_training_overlap"] is False
    bad.write_text(json.dumps({"min_pass_rate": True}))
    with pytest.raises(ValueError, match="min_pass_rate"):
        rg.load_policy(bad)
    bad.write_text(json.dumps({"require_no_training_overlap": 1}))
    with pytest.raises(ValueError, match="require_no_training_overlap"):
        rg.load_policy(bad)
