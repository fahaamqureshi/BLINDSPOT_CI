"""Build a clean submission ZIP: allowlisted files only, with a secret scan.

Usage: python scripts/package.py
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE_DIRS = ["blindspot_ci", "tests", "docs", "fixtures", "data", "datasets", "scripts", ".github"]
INCLUDE_FILES = ["README.md", "LICENSE", "pyproject.toml", "setup.py", "MANIFEST.in",
                 ".env.example", ".gitignore", "Dockerfile", ".dockerignore"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", ".blindspot-cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".jsonl"}
# Private labeled photos and run reports never go into a shared ZIP.
PRIVATE_PARTS = {"real", "real_manifest.json", "generated", "generated_manifest.json",
                 "open", "open_manifest.json", "hard", "hard_manifest.json", "video", "video_manifest.json", "coco", "coco_manifest.json", "corrupted", "corrupted_manifest.json", ".blindspot-runs"}
SECRET_PATTERNS = [
    re.compile(r"MODEL_API_KEY[ \t]*=[ \t]*[^\s#]+"),
    re.compile(r"(?i)bearer\s+[a-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def collect() -> list[Path]:
    files = [ROOT / name for name in INCLUDE_FILES
             if (ROOT / name).is_file() and not (ROOT / name).is_symlink()]
    for directory in INCLUDE_DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            if (path.is_file() and not path.is_symlink()
                    and not ((SKIP_PARTS | PRIVATE_PARTS) & set(path.parts))
                    and path.suffix not in SKIP_SUFFIXES):
                files.append(path)
    return files


def find_secrets(files: list[Path]) -> list[str]:
    hits = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")
    return hits


def main() -> int:
    files = collect()
    hits = find_secrets(files)
    if hits:
        print("Refusing to package. Possible secrets found:", *hits, sep="\n  ")
        return 1
    version = re.search(r'version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    target = out_dir / f"blindspot-ci-{version.group(1) if version else 'dev'}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"Wrote {target} with {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
