"""Local labeling tool: a person draws the box. No model ever sees or proposes a label here.

Photos are served upright (EXIF rotation applied) at full size, so the pixel numbers a person draws
are exactly the numbers the importer checks. Labels are written to a JSON file in the importer format.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from blindspot_ci.experiment.cases import IMAGE_SUFFIXES, VISIBILITIES
from blindspot_ci.fsutil import atomic_write_text
from blindspot_ci.security import install_local_guard

WEB = Path(__file__).parent / "web"
CONDITIONS = ["normal", "low_light", "angle", "occlusion", "absent", "unknown", "other"]


class LabelRequest(BaseModel):
    name: str
    condition: str = Field(default="normal")
    visibility: str
    bbox: list[int] | None = None
    note: str = Field(default="", max_length=300)


def _upright(path: Path) -> Image.Image:
    with Image.open(path) as raw:
        raw.load()
        return ImageOps.exif_transpose(raw).convert("RGB")


def create_app(folder: Path, out: Path, annotator: str, concept: str = "red safety tag") -> FastAPI:
    folder = folder.resolve()
    files = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not files:
        raise ValueError(f"no jpg or png photos in {folder}")
    if not annotator.strip():
        raise ValueError("annotator name is required: a person must own every label")
    app = FastAPI(title="BLINDSPOT labeler")
    install_local_guard(app)

    def load() -> dict[str, Any]:
        if out.is_file():
            try:
                return {c["image_source"]: c
                        for c in json.loads(out.read_text(encoding="utf-8"))["cases"]}
            except (json.JSONDecodeError, OSError, KeyError, TypeError):
                return {}  # a damaged labels file must not brick the tool; the next save rewrites it
        return {}

    def known(name: str) -> Path:
        if name not in files:
            raise HTTPException(404, "photo not in the chosen folder")
        return folder / name

    @app.get("/")
    def page() -> FileResponse:
        return FileResponse(WEB / "labeler.html")

    @app.get("/api/images")
    def images() -> dict[str, Any]:
        done = load()
        return {"annotator": annotator, "concept": concept, "conditions": CONDITIONS,
                "images": [{"name": n, "labeled": str(folder / n) in done} for n in files]}

    @app.get("/api/image/{name}")
    def image(name: str) -> Response:
        buffer = io.BytesIO()
        _upright(known(name)).save(buffer, "JPEG", quality=92)
        return Response(buffer.getvalue(), media_type="image/jpeg")

    @app.get("/api/label/{name}")
    def label(name: str) -> dict[str, Any]:
        return load().get(str(known(name)), {})

    @app.post("/api/label")
    def save(request: LabelRequest) -> dict[str, Any]:
        path = known(request.name)
        if request.visibility not in VISIBILITIES or request.condition not in CONDITIONS:
            raise HTTPException(422, "unknown visibility or condition")
        width, height = _upright(path).size
        box = request.bbox
        if request.visibility == "visible":
            if not box or len(box) != 4 or not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                raise HTTPException(422, f"a visible photo needs a box inside the {width}x{height} photo")
        elif box:
            raise HTTPException(422, "only a visible photo has a box")
        cases = load()
        stem = re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)[:40]
        case = {"id": f"tray_{stem}", "title": f"{concept} ({request.condition.replace('_', ' ')})",
                "image_source": str(path), "condition": request.condition, "concept": concept,
                "ground_truth": {"visibility": request.visibility, "bbox": box if request.visibility == "visible" else None},
                "label_provenance": {"annotator": annotator, "labeled_at": datetime.now(timezone.utc).isoformat(),
                                     "reviewer": "", "tool": "blindspot_ci.labeler (box drawn by a person)"},
                "recovery_case": None, "note": request.note}
        cases[str(path)] = case
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, json.dumps({"cases": list(cases.values())}, indent=2))
        return {"saved": case["id"], "total": len(cases), "of": len(files)}

    return app
