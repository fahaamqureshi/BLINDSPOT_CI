"""Offline setup diagnostics. No provider is constructed and no model is called."""
from __future__ import annotations

import os
from pathlib import Path

from blindspot_ci.config import ConfigurationError, Settings


def _writable(path: Path, directory: bool) -> bool:
    if path.exists() and (path.is_symlink() or path.is_dir() != directory):
        return False
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    if current != path and not current.is_dir():
        return False
    return os.access(current, os.W_OK)


def inspect_setup() -> dict:
    checks = []

    def record(name, passed, detail):
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    try:
        cfg = Settings()
    except ConfigurationError as exc:
        record("configuration", False, str(exc))
        return {"ok": False, "network_calls": 0, "checks": checks}
    record("configuration", True,
           f"provider={cfg.provider}; planner={cfg.planner}; live_enabled={cfg.live_api_enabled}")
    root = os.environ.get("BLINDSPOT_WORKSPACE")
    if root:
        from blindspot_ci.workspace import validate_workspace
        try:
            validate_workspace(Path(root).expanduser().resolve())
            record("workspace", True, str(Path(root).expanduser().resolve()))
        except ValueError as exc:
            record("workspace", False, str(exc))
    try:
        from blindspot_ci.experiment.cases import load_named_dataset
        data = load_named_dataset(cfg.dataset)
        record("dataset", bool(data.cases), f"{len(data.cases)} validated cases in {cfg.dataset}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        record("dataset", False, str(exc))
    for name, path, directory in [("runs", cfg.runs_dir, True), ("cache", cfg.cache_dir, True),
                                  ("provenance", cfg.provenance_path, False)]:
        record(name, _writable(path, directory), str(path.resolve()))
    return {"ok": all(c["status"] == "PASS" for c in checks), "network_calls": 0,
            "notice": "Offline setup check only. No inference, credential test or model performance claim.",
            "checks": checks}
