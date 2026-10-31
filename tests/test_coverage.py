from blindspot_ci import cli
from blindspot_ci.experiment.cases import Dataset, InspectionCase
from blindspot_ci.experiment.coverage import MIN_CASES_PER_CELL, build_matrix, load_matrix, render


def _ds(kind, conditions):
    cases = {f"c{i:03d}": InspectionCase(f"c{i:03d}", "t", "x.png", cond, "tag", "visible")
             for i, cond in enumerate(conditions)}
    return Dataset("d", kind, "x", cases)


def test_counts_empty_and_thin_cells():
    m = build_matrix({"real": _ds("REAL", ["normal"] * MIN_CASES_PER_CELL + ["low_light"])})
    cells = m["rows"]["real"]["cells"]
    assert cells["normal"] == MIN_CASES_PER_CELL and cells["low_light"] == 1 and cells["absent"] == 0
    assert "real/absent" in m["empty"]
    assert "real/low_light" in m["thin"] and "real/normal" not in m["thin"]
    assert m["rows"]["real"]["total"] == MIN_CASES_PER_CELL + 1
    assert m["condition_totals"]["low_light"] == 1


def test_extra_condition_and_sorted_deterministic_output():
    a = {"b": _ds("REAL", ["glare"]), "a": _ds("SYNTHETIC_X", ["normal"])}
    m1, m2 = build_matrix(a), build_matrix(dict(reversed(list(a.items()))))
    assert render(m1) == render(m2) and "glare" in m1["conditions"]
    assert list(m1["rows"]) == ["a", "b"] and m1["conditions"] == sorted(m1["conditions"])
    out = render(m1, "markdown")
    assert "a (synthetic)" in out and "not real evidence" in out and "c000" not in out


def test_unavailable_dataset_reported():
    out = render(build_matrix({}, {"real": "no manifest"}))
    assert "Unavailable: real (no manifest)." in out


def test_missing_dataset_does_not_crash(monkeypatch):
    def boom(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr("blindspot_ci.experiment.coverage.MANIFESTS", {"ghost": None})
    monkeypatch.setattr("blindspot_ci.experiment.coverage.load_named_dataset", boom)
    assert load_matrix()["unavailable"] == {"ghost": "no manifest"}


def test_cli_exit_code_zero(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["blindspot", "coverage"])
    cli.main()
    assert "Empty cells" in capsys.readouterr().out


def test_severity_variants_grouped_into_family():
    m = build_matrix({"real": _ds("REAL", ["blur_s3", "blur_s5", "contrast_s3", "jpeg_s5",
                                          "low_light_s3", "low_light_s5", "lookalike", "lookalike_scene"])})
    cells = m["rows"]["real"]["cells"]
    assert cells["blur"] == 2 and cells["contrast"] == 1 and cells["jpeg"] == 1 and cells["low_light"] == 2
    assert cells["lookalike"] == 1 and cells["lookalike_scene"] == 1
    assert not any("_s3" in c or "_s5" in c for c in m["conditions"])


def test_pooled_excludes_synthetic_and_derived():
    m = build_matrix({"a": _ds("REAL", ["normal"] * 3), "b": _ds("REAL", ["normal"] * 2 + ["blur_s3"]),
                      "syn": _ds("SYNTHETIC_X", ["normal"] * 9), "corrupted": _ds("REAL", ["normal"] * 7),
                      "generated": _ds("REAL", ["normal"] * 5)})
    assert m["pooled"]["normal"] == 5 and m["pooled"]["blur"] == 1 and m["pooled_datasets"] == 2
    out = render(m)
    assert "Pooled totals" in out and "different photos and labelers; read as a rough guide." in out
    assert "blur 1*" in out
    assert "no independent real datasets" in render(build_matrix({"syn": _ds("SYNTHETIC_X", ["normal"])}))


def test_empty_list_is_compact():
    m = build_matrix({"real": _ds("REAL", ["normal", "blur_s3"]), "none": _ds("REAL", []),
                      "other": _ds("REAL", ["normal"])})
    assert "real/absent" in m["empty"] and "real/blur" not in m["empty"]
    assert not any(e.startswith("none/") for e in m["empty"])
    total_empty = sum(1 for r in m["rows"].values() for v in r["cells"].values() if v == 0)
    assert m["other_empty"] == total_empty - len(m["empty"]) and m["other_empty"] > 0
    assert f"plus {m['other_empty']} other empty cells" in render(m)
