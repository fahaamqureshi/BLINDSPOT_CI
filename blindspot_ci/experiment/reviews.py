"""Reviewer notes and the Muse Wonder audit, saved beside a run report without touching its scores."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blindspot_ci.fsutil import FILE_LOCK, atomic_write_text

RUN_ID = re.compile(r"^[0-9a-f]{16}$")
MAX_NOTES_PER_RUN = 100
MAX_NOTE = 1000
NOTE_SOURCES = {"typed", "MUSE_VOICE_TRANSCRIBE"}


def _path(runs_dir: Path, run_id: str) -> Path:
    if not RUN_ID.match(run_id):
        raise ValueError("invalid run id")
    if not (runs_dir / f"{run_id}.json").is_file():
        raise FileNotFoundError(run_id)
    return runs_dir / f"{run_id}.extras.json"


def load_extras(runs_dir: Path, run_id: str) -> dict[str, Any]:
    path = _path(runs_dir, run_id)
    if path.is_file():
        try:
            extras = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"reviewer_notes": [], "audit": None}  # a damaged sidecar is a miss, like the cache
        if isinstance(extras, dict):
            notes = extras.get("reviewer_notes")
            if not isinstance(notes, list):
                notes = []
            valid_notes = [
                {key: note[key] for key in ("case_id", "text", "source", "at")}
                for note in notes if isinstance(note, dict)
                and all(isinstance(note.get(key), str) for key in ("case_id", "text", "source", "at"))
                and note["source"] in NOTE_SOURCES and 0 < len(note["text"]) <= MAX_NOTE
            ][:MAX_NOTES_PER_RUN]
            audit = extras.get("audit")
            if not isinstance(audit, dict) or not isinstance(audit.get("text"), str):
                audit = None
            else:
                audit = {key: audit[key] for key in ("text", "model", "at", "note")
                         if isinstance(audit.get(key), str)}
            # Only reviewer fields may be merged into a saved evaluation report.
            return {"reviewer_notes": valid_notes, "audit": audit}
        return {"reviewer_notes": [], "audit": None}
    return {"reviewer_notes": [], "audit": None}


def _save(runs_dir: Path, run_id: str, extras: dict[str, Any]) -> None:
    atomic_write_text(_path(runs_dir, run_id), json.dumps(extras, indent=2))


def add_note(runs_dir: Path, run_id: str, case_id: str, text: str, source: str) -> dict[str, Any]:
    text = text.strip()
    if source not in NOTE_SOURCES:
        raise ValueError("unknown note source")
    if not text or len(text) > MAX_NOTE:
        raise ValueError(f"a note needs 1 to {MAX_NOTE} characters")
    run = json.loads((runs_dir / f"{run_id}.json").read_text(encoding="utf-8")) if RUN_ID.match(run_id) else {}
    if case_id not in {s["case"]["id"] for s in run.get("steps", [])}:
        raise ValueError("case was not part of this run")
    with FILE_LOCK:
        return _append_note(runs_dir, run_id, case_id, text, source)


def _append_note(runs_dir: Path, run_id: str, case_id: str, text: str, source: str) -> dict[str, Any]:
    extras = load_extras(runs_dir, run_id)
    if len(extras["reviewer_notes"]) >= MAX_NOTES_PER_RUN:
        raise ValueError(f"a run holds at most {MAX_NOTES_PER_RUN} notes")
    note = {"case_id": case_id, "text": text, "source": source,
            "at": datetime.now(timezone.utc).isoformat()}
    extras["reviewer_notes"].append(note)
    _save(runs_dir, run_id, extras)
    return note


def save_audit(runs_dir: Path, run_id: str, text: str, model: str) -> dict[str, Any]:
    extras = load_extras(runs_dir, run_id)
    extras["audit"] = {"text": text, "model": model, "at": datetime.now(timezone.utc).isoformat(),
                       "note": "Written by Muse Wonder from the saved results. It does not change any score."}
    _save(runs_dir, run_id, extras)
    return extras["audit"]
