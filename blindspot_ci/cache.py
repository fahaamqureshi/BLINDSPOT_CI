from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from blindspot_ci.fsutil import atomic_write_text


class JsonCache:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None  # a damaged entry is a miss, not a permanent error

    def put(self, key: str, value: Any) -> None:
        atomic_write_text(self._path(key), json.dumps(value, sort_keys=True, indent=2))
