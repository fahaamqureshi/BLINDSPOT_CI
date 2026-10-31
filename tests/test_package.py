import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "package.py"


def load():
    spec = importlib.util.spec_from_file_location("package_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_never_includes_env_or_caches():
    names = {p.name for p in load().collect()}
    assert ".env" not in names
    assert not any(n.endswith(".jsonl") for n in names)


def test_secret_scan_flags_a_key(tmp_path):
    module = load()
    bad = tmp_path / "x.txt"
    bad.write_text("MODEL_API" + "_KEY=abcd1234", encoding="utf-8")
    module.ROOT = tmp_path
    assert module.find_secrets([bad])


def test_package_excludes_private_photos_but_keeps_synthetic_samples():
    module = load()
    paths = [p.relative_to(module.ROOT).as_posix() for p in module.collect()]
    assert "datasets/manifest.json" in paths
    assert any(p.startswith("datasets/samples/") for p in paths)
    assert not any(p.startswith("datasets/real/") or p.endswith("real_manifest.json") for p in paths)


def test_private_import_is_skipped_even_if_present(tmp_path):
    module = load()
    (tmp_path / "datasets" / "real").mkdir(parents=True)
    (tmp_path / "datasets" / "real" / "x.png").write_bytes(b"x")
    (tmp_path / "datasets" / "real_manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "datasets" / "manifest.json").write_text("{}", encoding="utf-8")
    module.ROOT = tmp_path
    module.INCLUDE_DIRS = ["datasets"]
    module.INCLUDE_FILES = []
    names = [p.name for p in module.collect()]
    assert names == ["manifest.json"]
