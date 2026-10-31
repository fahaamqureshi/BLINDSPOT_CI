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
