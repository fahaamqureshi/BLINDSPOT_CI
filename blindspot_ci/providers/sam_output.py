from __future__ import annotations

from typing import Any

from blindspot_ci.models import Detection

try:  # Official Meta parser; install with: pip install -e ".[live]"
    from meta_sam_parser import (
        CompletedOutcome,
        InvalidSegmentationMaskError,
        decode_mask_to_svg_path,
        image_segmentation_format,
    )

    PARSER_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the extra is missing
    PARSER_AVAILABLE = False

# parser_status values. Only "structured" lets a run finish without a review note.
STRUCTURED = "structured"
UNPARSED_TEXT = "unparsed_text"
PARSED_WITH_ERRORS = "parsed_with_errors"
PARSER_UNAVAILABLE = "parser_unavailable"


def _mask_metadata(record: Any, notes: list[str]) -> dict[str, Any]:
    """Mask facts a viewer needs to draw it on the photo.

    SAM masks are box-local: the raster covers only its box. The SVG path uses raster pixel
    coordinates, so draw it with translate(left, top) scale((right-left)/width, (bottom-top)/height).
    """
    mask, bounds = record.mask, record.bounds
    info: dict[str, Any] = {
        "encoding": mask.encoding, "width": mask.width, "height": mask.height,
        "bounds_xyxy": [bounds.left, bounds.top, bounds.right, bounds.bottom],
    }
    if mask.width != bounds.right - bounds.left or mask.height != bounds.bottom - bounds.top:
        notes.append("warning:mask_size_differs_from_bounds")
    try:
        info["svg_path"] = decode_mask_to_svg_path(mask)
    except (InvalidSegmentationMaskError, RuntimeError) as exc:  # keep the box, note the lost mask
        notes.append(f"warning:mask_not_drawable:{type(exc).__name__}")
    return info


def parse_sam_output(text: str, probe: str, source: str) -> tuple[list[Detection], str, list[str]]:
    """Turn SAM 3.1 special-token text into detections using Meta's official parser.

    One probe is one text prompt, so every box found is a detection labelled with that probe.
    An empty response means no match and is a valid structured result. The box confidence is
    kept as None when the API omits it; this code never invents a score. Masks are validated by
    the parser, and only their size and encoding are kept in metadata.
    """
    if not PARSER_AVAILABLE:
        return [], PARSER_UNAVAILABLE, ["meta-sam-parser is not installed"]
    if not isinstance(text, str):
        return [], PARSED_WITH_ERRORS, ["error:parser_input_not_text"]
    try:
        parser = image_segmentation_format().create_parser()
        parser.push(text)
        result = parser.finish(CompletedOutcome()).result
    except Exception as exc:  # noqa: BLE001 - a parser failure is flagged for review, never read as a no-match
        return [], PARSED_WITH_ERRORS, [f"error:parser_failed:{type(exc).__name__}"]
    detections: list[Detection] = []
    unmatched: dict[str, list[Detection]] = {}  # object_id -> boxes still waiting for their mask
    notes_out: list[str] = []
    text_lines = 0
    for record in result.records:  # wire order is box then mask, so pair in that order
        if record.kind == "text":
            text_lines += 1
        elif record.kind == "box":
            detection = Detection(label=probe, confidence=record.confidence, source=source, metadata={
                "object_id": record.object_id,
                "box_xyxy": [record.left, record.top, record.right, record.bottom],
            })
            detections.append(detection)
            unmatched.setdefault(record.object_id, []).append(detection)
        elif record.kind == "mask":
            waiting = unmatched.get(record.object_id) or []
            if not waiting:
                notes_out.append(f"warning:mask_without_box:{record.object_id}")
                continue
            detection = waiting.pop(0)
            detection.metadata["mask"] = _mask_metadata(record, notes_out)
            bounds = record.bounds
            if [bounds.left, bounds.top, bounds.right, bounds.bottom] != detection.metadata["box_xyxy"]:
                notes_out.append(f"warning:mask_bounds_differ_from_box:{record.object_id}")
    for object_id, waiting in unmatched.items():
        notes_out.extend(f"warning:box_without_mask:{object_id}" for _ in waiting)
    notes = [f"{d.severity}:{d.code}" for d in result.diagnostics] + notes_out
    if any(d.severity == "error" for d in result.diagnostics):
        return detections, PARSED_WITH_ERRORS, notes
    if text_lines and not detections:
        return detections, UNPARSED_TEXT, ["response had text but no segmentation records"]
    return detections, STRUCTURED, notes
