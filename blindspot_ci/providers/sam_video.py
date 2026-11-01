from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from blindspot_ci.budget import BudgetGuard
from blindspot_ci.providers.meta import MetaApiError, _MetaBase

# Pricing and limits from https://dev.meta.ai/docs/pricing-rate-limits and the SAM docs.
VIDEO_USD_PER_FRAME = 0.20 / 1000
VIDEO_MIN_BILLED_FRAMES = 50
VIDEO_MAX_FRAMES = 15000
VIDEO_UPLOAD_MAX_BYTES = 1_073_741_824
MAX_PROMPTED_OBJECTS = 16
PROPAGATION_DIRECTIONS = ("both", "forward", "backward")

_FRAME = re.compile(r"^<(\d+)f>")
_BOX = re.compile(r"(\d+)<\|box;([^|]*)\|>")
_RECORD_SPLIT = re.compile(r"(?<=\|>),(?=\d+<\|box;)")
_FRAME_SPLIT = re.compile(r"(?<=\|>)(?=<\d+f>)")


def billable_frames(frames: int) -> int:
    """Frames a request is billed for: the 50-frame minimum applies to short clips."""
    return max(int(frames), VIDEO_MIN_BILLED_FRAMES)


def estimate_cost(frames: int) -> float:
    if frames < 1 or frames > VIDEO_MAX_FRAMES:
        raise ValueError(f"frames must be between 1 and {VIDEO_MAX_FRAMES}")
    return billable_frames(frames) * VIDEO_USD_PER_FRAME


def reserve_cost(guard: BudgetGuard, frames: int) -> float:
    """Reserve the worst-case cost on the shared guard BEFORE the paid call. Raises BudgetExceeded."""
    cost = estimate_cost(frames)
    guard.reserve(cost)
    return cost


@dataclass(frozen=True)
class VideoBoxPrompt:
    """One box seed. The box is [x1, y1, x2, y2] in source pixels with x2 and y2 inclusive."""
    label: str
    box_xyxy: tuple[int, int, int, int]
    frame_index: int


@dataclass
class VideoRequest:
    body: dict[str, Any]
    id_to_label: dict[int, str]


def build_video_request(prompts: list[VideoBoxPrompt], *, frame_width: int, frame_height: int,
                        video_url: str | None = None, file_id: str | None = None,
                        propagation_direction: str = "both") -> VideoRequest:
    """Build a streaming SAM 3.1 video request seeded with box prompts.

    The API names objects by integer id, so each distinct label gets an id in order of first use
    and the mapping is returned to translate results back. Reusing a label on a later frame
    prompts the same object again. Masks cannot be switched off; box prompts always return
    one_bit masks, the smallest encoding.
    """
    if bool(video_url) == bool(file_id):
        raise ValueError("give exactly one of video_url or file_id")
    if propagation_direction not in PROPAGATION_DIRECTIONS:
        raise ValueError(f"propagation_direction must be one of {PROPAGATION_DIRECTIONS}")
    if not prompts:
        raise ValueError("at least one box prompt is required")
    if frame_width < 1 or frame_height < 1:
        raise ValueError("frame_width and frame_height must be positive")
    ids: dict[str, int] = {}
    for p in prompts:
        ids.setdefault(p.label, len(ids) + 1)
    if len(ids) > MAX_PROMPTED_OBJECTS:
        raise ValueError(f"at most {MAX_PROMPTED_OBJECTS} objects can be prompted, got {len(ids)}")
    by_frame: dict[int, dict[int, VideoBoxPrompt]] = {}
    for p in prompts:
        x1, y1, x2, y2 = p.box_xyxy
        if p.frame_index < 0:
            raise ValueError("frame_index must be zero or more")
        if not (0 <= x1 <= x2 < frame_width and 0 <= y1 <= y2 < frame_height):
            raise ValueError(f"box {p.box_xyxy} for {p.label!r} is outside the {frame_width}x{frame_height} frame")
        frame = by_frame.setdefault(p.frame_index, {})
        if ids[p.label] in frame:
            raise ValueError(f"object {p.label!r} has more than one box on frame {p.frame_index}")
        frame[ids[p.label]] = p
    if propagation_direction == "backward" and min(by_frame) == 0:
        raise ValueError("backward propagation needs a prompt on a frame after frame 0")
    parts = []
    for frame_index in sorted(by_frame):
        objs = ",".join(
            f"{oid}<|box;x1={p.box_xyxy[0]};y1={p.box_xyxy[1]};x2={p.box_xyxy[2]};y2={p.box_xyxy[3]}"
            f";w={frame_width};h={frame_height}|>"
            for oid, p in sorted(by_frame[frame_index].items()))
        parts.append(f"<{frame_index}f>{objs}")
    video_part = {"type": "input_video", **({"video_url": video_url} if video_url else {"file_id": file_id})}
    body = {
        "model": "sam-3.1",
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "".join(parts)}, video_part]}],
        "stream": True,
        "store": False,
        "metadata": {"propagation_direction": propagation_direction, "include_confidence": "true",
                     "mask_encoding": "one_bit"},
    }
    return VideoRequest(body=body, id_to_label={v: k for k, v in ids.items()})


@dataclass
class VideoFrame:
    frame_index: int
    objects: list[dict[str, Any]]  # {object_id, box_xyxy_pixels, confidence}

    def to_dict(self) -> dict[str, Any]:
        return {"frame_index": self.frame_index, "objects": self.objects}


@dataclass
class VideoParse:
    frames: list[VideoFrame] = field(default_factory=list)  # arrival order; frames are never merged
    malformed: int = 0
    duplicate_frames: list[int] = field(default_factory=list)  # indices seen more than once
    out_of_order: bool = False  # informational: tracking with direction "both" returns frames out of order
    truncated: bool = False  # stream ended before response.completed
    completed: bool = False
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _parse_record(chunk: str) -> dict[str, Any] | None:
    m = _BOX.match(chunk.strip())
    if not m:
        return None
    try:
        fields = dict(kv.split("=", 1) for kv in m.group(2).split(";"))
        x1, y1, x2, y2 = (int(fields[k]) for k in ("x1", "y1", "x2", "y2"))
        conf = float(fields["c"]) if "c" in fields else None
        frame_size = ([int(fields["w"]), int(fields["h"])]
                      if "w" in fields and "h" in fields else None)
    except (KeyError, ValueError):
        return None
    if x1 > x2 or y1 > y2:
        return None
    if frame_size is not None and (frame_size[0] < 1 or frame_size[1] < 1):
        return None
    record = {"object_id": int(m.group(1)), "box_xyxy_pixels": [x1, y1, x2, y2], "confidence": conf}
    if frame_size is not None:
        record["frame_size"] = frame_size
    return record


def _parse_line(line: str, out: VideoParse, seen: set[int]) -> None:
    line = line.strip()
    if not line:
        return
    marker = _FRAME.match(line)
    if not marker:
        out.malformed += 1
        return
    frame_index, rest = int(marker.group(1)), line[marker.end():]
    objects, bad = [], 0
    for chunk in _RECORD_SPLIT.split(rest) if rest else []:
        record = _parse_record(chunk)
        if record is None:
            bad += 1
        else:
            objects.append(record)
    out.malformed += bad
    if bad and not objects:
        return  # nothing trustworthy for this frame
    if frame_index in seen and frame_index not in out.duplicate_frames:
        out.duplicate_frames.append(frame_index)
    seen.add(frame_index)
    if out.frames and frame_index < out.frames[-1].frame_index:
        out.out_of_order = True
    out.frames.append(VideoFrame(frame_index, objects))


def parse_video_text(text: str) -> VideoParse:
    """Parse streamed output text into per-frame records.

    Frames are split on newlines, or on a frame marker that directly follows a closing token.
    A frame with a marker and no records is kept as an empty frame. Lines that are not frame
    records are skipped and counted. Two frames are never merged, even with the same index.
    """
    out, seen = VideoParse(), set()
    for line in text.splitlines():
        for piece in _FRAME_SPLIT.split(line):
            _parse_line(piece, out, seen)
    return out


def parse_video_stream(lines) -> VideoParse:
    """Parse server-sent event lines. Each output_text delta is parsed as its own frame line."""
    out, seen = VideoParse(), set()
    for raw in lines:
        if not raw.startswith("data:"):
            continue
        data = raw[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            out.malformed += 1
            continue
        kind = event.get("type", "") if isinstance(event, dict) else ""
        if kind == "response.output_text.delta":
            for line in str(event.get("delta", "")).splitlines():
                for piece in _FRAME_SPLIT.split(line):
                    _parse_line(piece, out, seen)
        elif kind == "response.completed":
            out.completed = True
            out.usage = (event.get("response") or {}).get("usage") or {}
        elif kind in {"response.failed", "error"}:
            detail = event.get("response", {}).get("error") if isinstance(event.get("response"), dict) else None
            out.error = json.dumps(detail or event.get("error") or event)[:300]
    out.truncated = not out.completed
    return out


@dataclass
class VideoResult:
    parse: VideoParse
    id_to_label: dict[int, str]
    reserved_usd: float
    billed_frames: int | None  # usage.video_frames_processed when the API reports it


class MetaSam31VideoAdapter(_MetaBase):
    """Paid SAM 3.1 video call. One attempt only: a failed request is never retried."""

    model = "sam-3.1"

    def __init__(self, api_key: str, base_url: str = "https://api.meta.ai/v1", timeout: float = 300.0,
                 transport: httpx.BaseTransport | None = None):
        super().__init__(api_key, base_url, timeout, retries=0)
        self.transport = transport

    def upload_file(self, path: str | Path) -> str:
        """Upload one MP4 for inference, with no retry and a pre-read size check."""
        file_path = Path(path)
        if file_path.suffix.lower() != ".mp4":
            raise ValueError("video upload requires an .mp4 file")
        size = file_path.stat().st_size
        if size > VIDEO_UPLOAD_MAX_BYTES:
            raise ValueError(f"video file is {size} bytes, above the {VIDEO_UPLOAD_MAX_BYTES} byte limit")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with file_path.open("rb") as handle, httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/files", headers=headers,
                                       data={"purpose": "user_data"},
                                       files={"file": (file_path.name, handle, "video/mp4")})
                if response.status_code >= 400:
                    response.read()
                    response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise MetaApiError(f"Meta API file upload failed (not retried): {self._describe(exc)}") from exc
        file_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(file_id, str) or not file_id:
            raise MetaApiError("Meta API file upload failed: response did not contain a file id")
        return file_id

    def delete_file(self, file_id: str) -> dict[str, Any]:
        """Delete an uploaded file once the inference request has finished."""
        if not file_id:
            raise ValueError("file_id is required")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                response = client.delete(f"{self.base_url}/files/{file_id}", headers=headers)
                if response.status_code >= 400:
                    response.read()
                    response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MetaApiError(f"Meta API file delete failed (not retried): {self._describe(exc)}") from exc
        if not isinstance(payload, dict):
            raise MetaApiError("Meta API file delete failed: response was not an object")
        return payload

    def track(self, request: VideoRequest, frames: int, budget: BudgetGuard) -> VideoResult:
        reserved = reserve_cost(budget, frames)  # raises BudgetExceeded before any network use
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                   "Accept": "text/event-stream"}
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout) as client,                     client.stream("POST", f"{self.base_url}/responses", headers=headers,
                                  json=request.body) as response:
                if response.status_code >= 400:
                    response.read()
                    response.raise_for_status()
                parsed = parse_video_stream(response.iter_lines())
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Meta API video request failed (not retried): {self._describe(exc)}") from exc
        if parsed.error:
            parsed.error = parsed.error.replace(self.api_key, "[redacted]")
        billed = parsed.usage.get("video_frames_processed")
        return VideoResult(parsed, request.id_to_label, reserved, billed if isinstance(billed, int) else None)
