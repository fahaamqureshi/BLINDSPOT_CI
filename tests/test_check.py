import importlib.util
import re
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check", Path(__file__).parents[1] / "scripts" / "check.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def test_clean_docs_pass():
    assert check.scan_docs_text("# Title\n\nPlain words, a list:\n- one\n", "a.md") == []


def test_each_banned_char_fails():
    for bad in ["a — b", "wait…", "wait...", "**bold**", "ok \U0001F600"]:
        assert check.scan_docs_text(f"line one\n{bad}\n", "a.md"), bad
    assert check.scan_docs_text("x\ny — z", "a.md")[0].startswith("a.md:2:")


def test_code_is_ignored():
    text = "```py\nx = a * b  # ...\n```\nUse `a * b...` here.\n~~~\n—\n~~~\n"
    assert check.scan_docs_text(text, "a.md") == []
    assert check.scan_docs_text("```\nx\n```\nafter *\n", "a.md") == ["a.md:4: asterisk"]


def test_scan_docs_reads_existing_files(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("fine\n", encoding="utf-8")
    (tmp_path / "docs" / "d.md").write_text("ok\nbad — dash\n", encoding="utf-8")
    assert check.scan_docs(tmp_path) == ["docs/d.md:2: em dash"]


def test_attribution_trailer_fails():
    assert check.scan_attribution("Fix bug\n\nCo-Authored-By: X <noreply@anthropic.com>")
    assert check.scan_attribution("Generated with a tool")
    assert check.scan_attribution("by noreply@openai.com")
    assert check.scan_attribution("Fix bug\n\nPlain message") == []


def test_attribution_skips_without_main(monkeypatch):
    monkeypatch.setattr(check, "run", lambda cmd: (False, ""))
    assert check.check_attribution()[0] is None


def test_attribution_uses_git_output(monkeypatch):
    def fake(cmd):
        return True, "msg\nCo-Authored-By: bot" if "log" in cmd else ""
    monkeypatch.setattr(check, "run", fake)
    assert check.check_attribution()[0] is False


def test_secret_hit_never_echoes_value(tmp_path):
    secret = "sk-" + "A" * 30
    (tmp_path / "f.txt").write_text(f"ok\nkey = {secret}\n", encoding="utf-8")
    (tmp_path / "g.txt").write_text("nothing\n", encoding="utf-8")
    hits = check.scan_secrets([tmp_path / "f.txt", tmp_path / "g.txt"],
                              [re.compile(r"sk-[A-Za-z0-9]{20,}")], tmp_path)
    assert hits == ["f.txt:2: secret-like string"]
    assert secret not in hits[0]
