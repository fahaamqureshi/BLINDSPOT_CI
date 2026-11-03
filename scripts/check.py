"""Completion gate: one command that proves a branch is done.

Usage: python scripts/check.py [--fast]   (--fast skips pytest)
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_NAMES = ["README.md", "AGENTS.md", "CLAUDE.md"]
BANNED_COMMIT = re.compile(
    r"Co-Authored-By|Generated with|noreply@anthropic\.com|noreply@openai\.com", re.IGNORECASE)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
STYLE_RULES = [
    ("em dash", re.compile("—")),
    ("ellipsis character", re.compile("…")),
    ("three dots", re.compile(r"\.\.\.")),
    ("asterisk", re.compile(r"\*")),
    ("emoji", EMOJI),
]


def prose_lines(text: str):
    """Yield (line_number, line) with fenced blocks dropped and inline code removed."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
            continue
        if fence is None:
            yield number, re.sub(r"`[^`]*`", "", line)


def scan_docs_text(text: str, name: str) -> list[str]:
    return [f"{name}:{number}: {label}"
            for number, line in prose_lines(text)
            for label, rule in STYLE_RULES if rule.search(line)]


def doc_files(root: Path = ROOT) -> list[Path]:
    found = [root / n for n in DOC_NAMES if (root / n).is_file()]
    return found + sorted((root / "docs").glob("*.md"))


def scan_docs(root: Path = ROOT) -> list[str]:
    hits = []
    for path in doc_files(root):
        hits += scan_docs_text(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())
    return hits


def scan_attribution(messages: str) -> list[str]:
    return [f"commit message line {n}: banned attribution"
            for n, line in enumerate(messages.splitlines(), 1) if BANNED_COMMIT.search(line)]


def scan_secrets(files: list[Path], patterns, root: Path = ROOT) -> list[str]:
    hits = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in patterns):
                hits.append(f"{path.relative_to(root).as_posix()}:{number}: secret-like string")
    return hits


def run(cmd: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def check_attribution() -> tuple[bool | None, list[str]]:
    ok, _ = run(["git", "rev-parse", "--verify", "--quiet", "main"])
    if not ok:
        return None, ["main not available, skipped"]
    ok, out = run(["git", "log", "main..HEAD", "--format=%B"])
    return (ok and not scan_attribution(out)), (scan_attribution(out) if ok else [out])


def check_secrets() -> tuple[bool, list[str]]:
    spec = importlib.util.spec_from_file_location("_package", ROOT / "scripts" / "package.py")
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    hits = scan_secrets(package.collect(), package.SECRET_PATTERNS)
    return not hits, hits


def main(argv: list[str]) -> int:
    fast = "--fast" in argv
    results: list[tuple[str, bool | None, list[str]]] = []
    ok, out = run([sys.executable, "-m", "ruff", "check", "blindspot_ci", "scripts", "tests", "setup.py"])
    results.append(("ruff", ok, [] if ok else out.splitlines()))
    if not fast:
        with tempfile.TemporaryDirectory() as base:
            ok, out = run([sys.executable, "-m", "pytest", f"--basetemp={base}/t",
                           "-p", "no:cacheprovider"])
        results.append(("pytest", ok, [] if ok else out.splitlines()[-30:]))
    docs = scan_docs()
    results.append(("docs style", not docs, docs))
    results.append(("attribution", *check_attribution()))
    ok, hits = check_secrets()
    results.append(("secrets", ok, hits))
    for name, ok, details in results:
        print(f"{'SKIP' if ok is None else 'PASS' if ok else 'FAIL'}  {name}")
        for detail in details:
            print(f"      {detail}")
    failed = [n for n, ok, _ in results if ok is False]
    print(f"\nSummary: {'FAIL (' + ', '.join(failed) + ')' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
