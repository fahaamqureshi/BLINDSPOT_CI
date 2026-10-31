"""Small file helpers: atomic writes so a crash or a second request never leaves a torn JSON file."""
from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

FILE_LOCK = threading.RLock()  # one writer at a time for the read-modify-write files


def atomic_write_text(path: Path, text: str) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
