"""Explicit, user-owned storage outside an installed package."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

MARKER = "blindspot-workspace.json"


def default_path(relative: str) -> Path:
    root = os.environ.get("BLINDSPOT_WORKSPACE")
    return Path(root).expanduser().resolve() / relative if root else Path(relative)


def validate_workspace(path: Path) -> None:
    marker = path / MARKER
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Workspace is not initialized: {path}. Run blindspot init PATH first.") from exc
    if not isinstance(data, dict) or data.get("format_version") != 1:
        raise ValueError("Unsupported workspace format. Choose a new workspace directory.")


def initialize(path: Path) -> Path:
    """Copy only distributable fixtures. Never replace existing user data."""
    from blindspot_ci.resources import PUBLIC_ROOT

    path = path.expanduser().resolve()
    if (path / MARKER).exists():
        validate_workspace(path)
        return path
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError("Choose an empty directory. Existing files will not be overwritten.")
    public = ["data/scenarios.json", "datasets/manifest.json", "datasets/real-labels-template.json",
              "fixtures/mock_responses.json", "fixtures/ground_truth.json", "fixtures/expected_demo.json",
              "fixtures/examples/8f6003378706480a.json", "fixtures/examples/a165cd6773cd433a.json",
              "fixtures/policies/long-video.json"]
    public += [f"datasets/samples/{name}.png"
               for name in ("absent", "alternate_view", "low_light", "normal", "occluded")]
    for name in public:
        if not (PUBLIC_ROOT / name).is_file():
            raise FileNotFoundError(f"Installed practice asset is missing: {name}. Reinstall the package.")
    path.mkdir(parents=True, exist_ok=True)
    for name in public:
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle, (PUBLIC_ROOT / name).open("rb") as source:
            shutil.copyfileobj(source, handle)
    (path / MARKER).write_text(json.dumps({"format_version": 1,
        "notice": "Practice data and scripted answers. Not model performance."}, indent=2), encoding="utf-8")
    return path
