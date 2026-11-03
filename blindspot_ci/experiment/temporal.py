"""Offline-first orchestration and reporting for the MOT20 long-video test."""
from __future__ import annotations

import hashlib
import json
import statistics
import time
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.experiment.runner import load_run
from blindspot_ci.experiment.scoring import (
    DEFAULT_MIN_IOU,
    ERROR,
    FALSE_NEGATIVE,
    LOCALIZATION,
    PASS,
    CaseOutcome,
    box_iou,
    summarize,
)
from blindspot_ci.fsutil import atomic_write_text
from blindspot_ci.providers.meta import MetaApiError
from blindspot_ci.providers.sam_video import (
    VIDEO_MIN_BILLED_FRAMES,
    VIDEO_USD_PER_FRAME,
    MetaSam31VideoAdapter,
    VideoBoxPrompt,
    VideoResult,
    build_video_request,
    parse_video_stream,
    reserve_cost,
)

CONDITION_PRIORITY = ("occluded", "truncated", "dark", "small_object", "normal")
DATASET_ID = "mot20-long"
DATASET_TYPE = "HUMAN_LABELED_VIDEO"
MAX_RAW_TEXT_BYTES = 3000 * 1024 * 1024
STREAM_IDLE_TIMEOUT_SECONDS = 180.0
STREAM_TOTAL_TIMEOUT_SECONDS = 25 * 60


class VideoRequestRefused(MetaApiError):
    """An HTTP refusal received before the video stream began processing."""

    def __init__(self, message: str, reserved_cost: float):
        super().__init__(message)
        self.reserved_cost = reserved_cost


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sequence_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sequences = manifest.get("sequences")
    if not isinstance(sequences, list) or not sequences:
        raise ValueError("manifest must contain a non-empty sequences list")
    result = {}
    for sequence in sequences:
        if not isinstance(sequence, dict) or not sequence.get("name"):
            raise ValueError("each manifest sequence needs a name")
        name = str(sequence["name"])
        if name in result:
            raise ValueError(f"manifest repeats sequence {name}")
        for field in ("source_url", "fps", "frame_size", "frame_count", "targets"):
            if field not in sequence:
                raise ValueError(f"{name}: manifest is missing {field}")
        if not isinstance(sequence["targets"], list) or not sequence["targets"]:
            raise ValueError(f"{name}: manifest needs at least one target")
        if len(sequence["targets"]) > 16:
            raise ValueError(f"{name}: at most 16 targets can be seeded")
        result[name] = sequence
    return result


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("manifest must hold a JSON object")
    _sequence_map(data)
    return data


def _target_label(target: dict[str, Any]) -> str:
    if "track_id" not in target:
        raise ValueError("each target needs a track_id")
    return str(target["track_id"])


def _rounded_int(value: Any) -> int:
    return round(float(value))


def _seed_prompts(sequence: dict[str, Any]) -> tuple[list[VideoBoxPrompt], int]:
    width, height = int(sequence["frame_size"][0]), int(sequence["frame_size"][1])
    prompts = []
    clamped_count = 0
    for target in sequence["targets"]:
        seed = target.get("seed_box")
        if not isinstance(seed, list) or len(seed) != 4:
            raise ValueError(f"target {_target_label(target)} has an invalid seed_box")
        original = tuple(_rounded_int(value) for value in seed)
        clamped = (
            max(0, min(original[0], width - 1)), max(0, min(original[1], height - 1)),
            max(0, min(original[2], width - 1)), max(0, min(original[3], height - 1)),
        )
        clamped_count += clamped != original
        prompts.append(VideoBoxPrompt(
            _target_label(target), clamped, int(target["seed_frame"])))
    return prompts, clamped_count


def build_sequence_request(sequence: dict[str, Any], *, file_id: str | None = None):
    """Build one validated request and count prompt boxes moved inside the frame."""
    prompts, clamped_count = _seed_prompts(sequence)
    request = build_video_request(
        prompts, frame_width=int(sequence["frame_size"][0]), frame_height=int(sequence["frame_size"][1]),
        video_url=None if file_id else str(sequence["source_url"]), file_id=file_id,
        propagation_direction="forward")
    return request, clamped_count


def _sequence_cost(frame_count: int) -> float:
    if frame_count < 1:
        raise ValueError("frame_count must be positive")
    return frame_count * VIDEO_USD_PER_FRAME


def plan_long_video(manifest: dict[str, Any], names: list[str], budget_usd: float) -> list[dict[str, Any]]:
    """Return the exact offline plan without constructing an adapter or using a network."""
    if budget_usd < 0:
        raise ValueError("budget_usd must not be negative")
    sequences = _sequence_map(manifest)
    if not names:
        raise ValueError("at least one sequence is required")
    if len(set(names)) != len(names):
        raise ValueError("a sequence may be named only once")
    plan = []
    for name in names:
        if name not in sequences:
            raise ValueError(f"sequence {name} is not in the manifest")
        sequence = sequences[name]
        frames = int(sequence["frame_count"])
        targets, _ = _seed_prompts(sequence)
        plan.append({"sequence": name, "frames": frames, "targets": len(targets),
                     "cost_usd": _sequence_cost(frames), "video_url": sequence["source_url"]})
    return plan


def _write_raw(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def _reserve_sequence_cost(guard: BudgetGuard, frames: int) -> float:
    """Use the provider rule for real clips and exact pricing for short fixtures."""
    if frames >= VIDEO_MIN_BILLED_FRAMES:
        return reserve_cost(guard, frames)
    cost = _sequence_cost(frames)
    guard.reserve(cost)
    return cost


def _monotonic() -> float:
    return time.monotonic()


def _is_output_text_delta(line: str) -> bool:
    if not line.startswith("data:"):
        return False
    try:
        event = json.loads(line[5:].strip())
    except json.JSONDecodeError:
        return False
    return isinstance(event, dict) and event.get("type") == "response.output_text.delta"


def _direct_video_call(adapter: MetaSam31VideoAdapter, request: Any, frames: int,
                       budget: BudgetGuard, raw_path: Path) -> VideoResult:
    """Make one request while streaming raw SSE text to disk and parsing it incrementally."""
    reserved = _reserve_sequence_cost(budget, frames)
    headers = {"Authorization": f"Bearer {adapter.api_key}", "Content-Type": "application/json",
               "Accept": "text/event-stream"}
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    stream_error: Exception | None = None
    cap_hit = False
    stall_hit = False
    raw_bytes = 0
    stream_started_at: float | None = None
    last_output_at: float | None = None

    def lines(response):
        nonlocal stream_error, cap_hit, stall_hit, raw_bytes, last_output_at
        try:
            for line in response.iter_lines():
                text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line)
                encoded = (text + "\n").encode("utf-8")
                remaining = MAX_RAW_TEXT_BYTES - raw_bytes
                if len(encoded) > remaining:
                    if remaining > 0:
                        raw_file.write(encoded[:remaining])
                        raw_file.flush()
                        raw_bytes += remaining
                    cap_hit = True
                    return
                raw_file.write(encoded)
                raw_file.flush()
                raw_bytes += len(encoded)
                now = _monotonic()
                if _is_output_text_delta(text):
                    last_output_at = now
                if ((stream_started_at is not None and now - stream_started_at > STREAM_TOTAL_TIMEOUT_SECONDS) or
                        (last_output_at is not None and now - last_output_at > STREAM_IDLE_TIMEOUT_SECONDS)):
                    stall_hit = True
                    return
                yield text
        except Exception as exc:  # noqa: BLE001
            stream_error = exc

    parsed = None
    try:
        with raw_path.open("wb") as raw_file, \
                httpx.Client(transport=adapter.transport, timeout=adapter.timeout) as client, \
                client.stream("POST", f"{adapter.base_url}/responses", headers=headers,
                              json=request.body) as response:
                if response.status_code >= 400:
                    body = response.read()
                    raw_file.write(body if isinstance(body, bytes) else str(body).encode("utf-8"))
                    raw_file.flush()
                    try:
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        raise VideoRequestRefused(
                            f"Meta API video request failed (not retried): {adapter._describe(exc)}",
                            reserved) from exc
                stream_started_at = _monotonic()
                last_output_at = stream_started_at
                parsed = parse_video_stream(lines(response))
    except httpx.HTTPError as exc:
        if parsed is None:
            parsed = parse_video_stream(())
        parsed.truncated = True
        parsed.completed = False
        stream_error = stream_error or exc
    if parsed is None:
        parsed = parse_video_stream(())
    if stream_error or cap_hit or stall_hit:
        parsed.truncated = True
        parsed.completed = False
    if parsed.error:
        parsed.error = parsed.error.replace(adapter.api_key, "[redacted]")
    billed = parsed.usage.get("video_frames_processed")
    return VideoResult(parsed, request.id_to_label, reserved,
                       billed if isinstance(billed, int) else None)


def _call_video(adapter: Any, request: Any, frames: int, budget: BudgetGuard, raw_path: Path) -> VideoResult:
    if isinstance(adapter, MetaSam31VideoAdapter):
        return _direct_video_call(adapter, request, frames, budget, raw_path)
    result = adapter.track(request, frames=frames, budget=budget)
    raw = getattr(result, "raw_text", None) or getattr(result.parse, "raw_text", None)
    if raw is None:
        raw = "\n".join(
            f"<{frame.frame_index}f>" + ",".join(
                f"{obj['object_id']}<|box;x1={obj['box_xyxy_pixels'][0]};y1={obj['box_xyxy_pixels'][1]};"
                f"x2={obj['box_xyxy_pixels'][2]};y2={obj['box_xyxy_pixels'][3]}|>"
                for obj in frame.objects)
            for frame in result.parse.frames)
    _write_raw(raw_path, str(raw))
    return result


def _raw_video_call(request: Any, raw_path: Path) -> VideoResult:
    with raw_path.open("r", encoding="utf-8", errors="replace") as raw_file:
        parsed = parse_video_stream(raw_file)
    return VideoResult(parsed, request.id_to_label, 0.0, None)


def _condition(tags: list[str]) -> str:
    for name in CONDITION_PRIORITY:
        if name in tags:
            return name
    return "normal"


def _box(value: Any) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("a box must contain four coordinates")
    return tuple(_rounded_int(item) for item in value)


def _scale_model_box(obj: dict[str, Any], request_frame_size: tuple[int, int] | None) -> list[int]:
    box = _box(obj["box_xyxy_pixels"])
    reported = obj.get("frame_size")
    if request_frame_size is None or not isinstance(reported, (list, tuple)) or len(reported) != 2:
        return list(box)
    source_width, source_height = int(reported[0]), int(reported[1])
    target_width, target_height = request_frame_size
    if source_width < 1 or source_height < 1:
        return list(box)
    return [round(box[0] * target_width / source_width), round(box[1] * target_height / source_height),
            round(box[2] * target_width / source_width), round(box[3] * target_height / source_height)]


def _reported_frame_sizes(parsed: Any) -> list[list[int]]:
    sizes = set()
    for frame in getattr(parsed, "frames", []):
        for obj in frame.objects:
            size = obj.get("frame_size")
            if isinstance(size, (list, tuple)) and len(size) == 2:
                sizes.add((int(size[0]), int(size[1])))
    return [list(size) for size in sorted(sizes)]


def _scale_factors(output_sizes: list[list[int]], request_frame_size: tuple[int, int]) -> tuple[Any, Any]:
    factors = [(round(request_frame_size[0] / width, 6), round(request_frame_size[1] / height, 6))
               for width, height in output_sizes]
    if not factors:
        return None, None
    if len(factors) == 1:
        return factors[0]
    return [factor[0] for factor in factors], [factor[1] for factor in factors]


def _matching_object(frame: Any, label: str, id_to_label: dict[int, str]) -> dict[str, Any] | None:
    for obj in frame.objects:
        object_id = obj.get("object_id")
        if id_to_label.get(object_id) == label or str(object_id) == label:
            return obj
    return None


def _score_target(target: dict[str, Any], parsed: Any, id_to_label: dict[int, str],
                  min_iou: float, failed: str | None = None,
                  request_frame_size: tuple[int, int] | None = None) -> tuple[dict[str, Any], list[CaseOutcome]]:
    first_frames = {}
    duplicate_count = 0
    for frame in parsed.frames:
        if frame.frame_index in first_frames:
            duplicate_count += 1
            continue
        first_frames[frame.frame_index] = frame
    rows = []
    outcomes: list[CaseOutcome] = []
    label = _target_label(target)
    last_arrived = max(first_frames, default=-1) if getattr(parsed, "truncated", False) else None
    for labeled in target["frames"]:
        frame_index = int(labeled["frame"])
        tags = list(labeled.get("tags") or [])
        base = {"frame": frame_index, "tags": tags, "human_box": labeled.get("box")}
        if labeled.get("status") != "SCORED":
            rows.append({**base, "status": "NOT_SCORED", "scoreable": False, "iou": None,
                         "model_box": None})
            continue
        case_id = f"{target.get('_sequence', 'sequence')}-{label}-{frame_index}"
        if failed:
            status, iou, reason, model_box = ERROR, None, failed, None
        elif last_arrived is not None and frame_index > last_arrived:
            status, iou, reason, model_box = ERROR, None, \
                "The stream ended early before this labeled frame.", None
        else:
            found = _matching_object(first_frames.get(frame_index), label, id_to_label) \
                if frame_index in first_frames else None
            if found is None:
                status, iou, reason, model_box = FALSE_NEGATIVE, 0.0, \
                    "The target was absent from the returned stream for this labeled frame.", None
            else:
                model_box = _scale_model_box(found, request_frame_size)
                iou = box_iou(_box(model_box), _box(labeled["box"]))
                if iou >= min_iou:
                    status, reason = PASS, f"Box overlap {iou:.2f} meets the {min_iou:.2f} threshold."
                else:
                    status, reason = LOCALIZATION, \
                        f"Box overlap {iou:.2f} is below the {min_iou:.2f} threshold."
        rows.append({**base, "status": status, "scoreable": status != ERROR, "iou": iou,
                     "reason": reason, "model_box": model_box})
        outcomes.append(CaseOutcome(case_id, status, status != ERROR, iou, reason))
    return {"target_id": target.get("track_id"), "seed_frame": target["seed_frame"],
            "frames": rows, "duplicate_count": duplicate_count,
            "held_for_whole_clip": bool(outcomes) and all(item.status == PASS for item in outcomes)}, outcomes


def _step(sequence_name: str, target: dict[str, Any], result: dict[str, Any], row: dict[str, Any],
          manifest_digest: str, source: str = "LIVE_META") -> dict[str, Any]:
    tags = row["tags"]
    condition = _condition(tags)
    case_id = f"{sequence_name}-{result['target_id']}-{row['frame']}"
    outcome = CaseOutcome(case_id, row["status"], row["scoreable"], row["iou"],
                          row.get("reason") or ("The frame was not labeled and was skipped." if not row["scoreable"] else
                          ("Target absent from the returned stream." if row["status"] == FALSE_NEGATIVE else
                           "Target box met the human-labeled overlap threshold." if row["status"] == PASS else
                           "Target box was returned below the overlap threshold.")))
    return {
        "case": {"id": case_id, "title": f"{sequence_name} target {result['target_id']} frame {row['frame']}",
                 "condition": condition, "tags": tags, "visibility": "visible",
                 "ground_truth_box": row["human_box"]},
        "decision": {"case_id": case_id, "reason": "one scored frame per target per 25 frames",
                     "planner": "SEEDED_BOX_TRACKING", "tool_call_id": None},
        "outcome": outcome.to_dict(),
        "ground_truth": {"visibility": "visible", "bbox": row["human_box"],
                         "label_provenance": {"source": "MOT20 human annotation"}},
        "prediction": {"source": source, "provider": "meta", "model": "sam-3.1",
                       "parser_status": "structured", "detections": ([{"bbox": row["model_box"]}]
                                                                            if row["model_box"] else [])},
        "image_sha256": hashlib.sha256(f"{manifest_digest}:{sequence_name}:{row['frame']}".encode()).hexdigest(),
    }


def _temporal_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / f"{run_id}.temporal.json"


def run_long_video(manifest: dict[str, Any], names: list[str], budget_usd: float,
                   min_iou: float = DEFAULT_MIN_IOU, *, runs_dir: Path = Path("artifacts/runs"),
                   raw_dir: Path | None = None, adapter: Any | None = None,
                   transport: httpx.BaseTransport | None = None,
                   run_id: str | None = None,
                   call: Callable[[Any, Any, int, BudgetGuard, Path], VideoResult] | None = None,
                   raw_input: Path | None = None, replayed_from_raw: bool = False,
                   video_file_id: str | None = None, video_file_uploaded: bool = False,
                   video_file_name: str | None = None, video_file_bytes: int | None = None) -> dict[str, Any]:
    """Run selected sequences. The caller is responsible for checking live settings."""
    plan = plan_long_video(manifest, names, budget_usd)
    sequences = _sequence_map(manifest)
    run_id = run_id or uuid.uuid4().hex[:16]
    raw_dir = raw_dir or Path("artifacts/video-raw")
    runs_dir = Path(runs_dir)
    guard = BudgetGuard(max_calls=len(plan), max_cost_usd=float(budget_usd))
    manifest_digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    steps: list[dict[str, Any]] = []
    temporal_sequences: list[dict[str, Any]] = []
    errors: list[str] = []
    total_estimated = 0.0
    started = _now()
    for item in plan:
        name = item["sequence"]
        sequence = sequences[name]
        request, clamped_count = build_sequence_request(sequence, file_id=video_file_id)
        raw_path = raw_dir / f"{run_id}-{name}.txt"
        sequence_result = {"name": name, "fps": int(sequence["fps"]),
                           "frame_count": int(sequence["frame_count"]),
                           "request_frame_size": [int(sequence["frame_size"][0]), int(sequence["frame_size"][1])],
                           "output_frame_size": [], "scale_x": None, "scale_y": None,
                           "luminance_samples": sequence.get("luminance_samples", []),
                           "seed_boxes_clamped": clamped_count, "targets": []}
        cost_before = guard.cost_usd
        try:
            if raw_input is not None:
                result = _raw_video_call(request, Path(raw_input))
            else:
                if adapter is None:
                    adapter = MetaSam31VideoAdapter("", transport=transport)
                result = (call or _call_video)(adapter, request, int(sequence["frame_count"]), guard, raw_path)
            total_estimated += (result.billed_frames * VIDEO_USD_PER_FRAME
                                if result.billed_frames is not None else result.reserved_usd)
            if result.parse.error:
                raise MetaApiError(result.parse.error)
            request_frame_size = (int(sequence["frame_size"][0]), int(sequence["frame_size"][1]))
            output_sizes = _reported_frame_sizes(result.parse)
            sequence_result["output_frame_size"] = output_sizes
            sequence_result["scale_x"], sequence_result["scale_y"] = _scale_factors(
                output_sizes, request_frame_size)
            for target in sequence["targets"]:
                scored_target, _ = _score_target(target, result.parse, result.id_to_label, min_iou,
                                                  request_frame_size=request_frame_size)
                scored_target["condition_counts"] = dict(Counter(
                    tag for row in scored_target["frames"] for tag in row["tags"]))
                sequence_result["targets"].append(scored_target)
                for row in scored_target["frames"]:
                    if row["status"] != "NOT_SCORED" and (int(row["frame"]) - int(target["seed_frame"])) % 25 == 0:
                        steps.append(_step(name, target, scored_target, row, manifest_digest,
                                           "CACHE_LIVE_META" if replayed_from_raw else "LIVE_META"))
        except (BudgetExceeded, MetaApiError, OSError, ValueError) as exc:
            if isinstance(exc, VideoRequestRefused):
                guard.release_cost(exc.reserved_cost)
            total_estimated += guard.cost_usd - cost_before
            note = "; request refused before processing, reservation released" \
                if isinstance(exc, VideoRequestRefused) else ""
            errors.append(f"{name}: {str(exc).replace(getattr(adapter, 'api_key', ''), '[redacted]')}{note}")
            for target in sequence["targets"]:
                scored_target, _ = _score_target(
                    target, type("Parsed", (), {"frames": []})(), {}, min_iou, str(exc))
                sequence_result["targets"].append(scored_target)
            temporal_sequences.append(sequence_result)
            break
        temporal_sequences.append(sequence_result)
    report = {
        "id": run_id, "started_at": started, "finished_at": _now(),
        "mode": "CACHE_LIVE_META" if replayed_from_raw else "LIVE_META",
        "provider": "meta", "model": "sam-3.1", "planner": "SEEDED_BOX_TRACKING",
        "planner_prompt_version": None,
        "dataset": {"id": DATASET_ID, "type": DATASET_TYPE, "annotation_status": "human_labeled"},
        "min_iou": min_iou, "steps": steps, "errors": errors,
        "summary": summarize([CaseOutcome(**step["outcome"]) for step in steps],
                              {step["outcome"]["case_id"]: step["case"]["condition"] for step in steps}, min_iou),
        "calls": guard.calls, "estimated_cost_usd": round(total_estimated or guard.cost_usd, 6),
    }
    if video_file_uploaded:
        report["video_file_uploaded"] = True
        report["video_file_deleted"] = False
        report["video_file_name"] = video_file_name
        report["video_file_bytes"] = video_file_bytes
    if replayed_from_raw:
        report["replayed_from_raw"] = str(raw_input)
    runs_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(runs_dir / f"{run_id}.json", json.dumps(report, indent=2))
    temporal = {"run_id": run_id, "dataset": DATASET_ID, "min_iou": min_iou,
                "estimated_cost_usd": report["estimated_cost_usd"], "sequences": temporal_sequences}
    atomic_write_text(_temporal_path(runs_dir, run_id), json.dumps(temporal, indent=2))
    return report


def _miss_runs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    runs: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") == FALSE_NEGATIVE or row.get("status") == LOCALIZATION:
            current.append(row)
        elif row.get("status") == PASS and current:
            runs.append({"misses": current, "recovery": row})
            current = []
    if current:
        runs.append({"misses": current, "recovery": None})
    return runs, sum(item["recovery"] is None for item in runs)


def _dropout(rows: list[dict[str, Any]], frame_count: int) -> list[tuple[int, int, float | None]]:
    bins = [[0, 0] for _ in range(10)]
    for row in rows:
        if row.get("status") not in {PASS, FALSE_NEGATIVE, LOCALIZATION}:
            continue
        bucket = min(9, max(0, int((int(row["frame"]) - 1) * 10 / frame_count)))
        bins[bucket][1] += 1
        bins[bucket][0] += row["status"] != PASS
    return [(misses, total, round(misses / total, 3) if total else None) for misses, total in bins]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _recovery_stat(value: float | None, fps: float) -> str:
    return "n/a" if value is None else f"{value:.1f} frames ({value / fps:.2f} seconds)"


def _failure_share(count: int, total: int) -> str:
    return "n/a" if not total else f"{count / total:.1%}"


def render_temporal_report(runs_dir: Path, run_id: str) -> str:
    """Render the saved temporal evidence without reading the manifest or using the network."""
    load_run(runs_dir, run_id)
    path = _temporal_path(Path(runs_dir), run_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    sequence_lines: list[str] = []
    total_targets = total_held = total_reliable = total_misses = 0
    all_retentions: list[float] = []
    for sequence in data.get("sequences", []):
        fps = float(sequence["fps"])
        all_rows = [row for target in sequence["targets"] for row in target["frames"]]
        miss_runs: list[dict[str, Any]] = []
        never = 0
        held = 0
        retentions: list[float] = []
        conditions: dict[str, list[int]] = {}
        for target in sequence["targets"]:
            rows = target["frames"]
            runs, never_count = _miss_runs(rows)
            miss_runs.extend(runs)
            never += never_count
            held += bool(target.get("held_for_whole_clip"))
            scored = [row for row in rows if row.get("status") in {PASS, FALSE_NEGATIVE, LOCALIZATION}]
            if scored:
                retentions.append(sum(row["status"] == PASS for row in scored) / len(scored))
            for row in rows:
                if row.get("status") in {PASS, FALSE_NEGATIVE, LOCALIZATION}:
                    for tag in row.get("tags", []) or ["normal"]:
                        cell = conditions.setdefault(tag, [0, 0])
                        cell[1] += 1
                        cell[0] += row["status"] == PASS
        longest = max((len(item["misses"]) for item in miss_runs), default=0)
        longest_seconds = longest / fps if fps else 0.0
        recovery_frames = [item["recovery"]["frame"] - item["misses"][0]["frame"]
                           for item in miss_runs if item["recovery"]]
        bins = _dropout(all_rows, int(sequence["frame_count"]))
        luminance = [float(item["mean_luminance"]) for item in sequence.get("luminance_samples", [])]
        lum = f"{min(luminance):.2f} to {max(luminance):.2f}" if luminance else "unavailable"
        condition_text = ", ".join(f"{name} {value[0]}/{value[1]}" for name, value in sorted(conditions.items())) or "none"
        recovery_median = _percentile([float(value) for value in recovery_frames], 0.5)
        recovery_p90 = _percentile([float(value) for value in recovery_frames], 0.9)
        recovery_longest = max(recovery_frames, default=None)
        recovery_text = (f"{len(miss_runs)} miss runs; recovery median {_recovery_stat(recovery_median, fps)}, "
                         f"90th percentile {_recovery_stat(recovery_p90, fps)}, "
                         f"longest {_recovery_stat(recovery_longest, fps)}; "
                         f"never recovered {never}.")
        false_negative = sum(row.get("status") == FALSE_NEGATIVE for row in all_rows)
        localization = sum(row.get("status") == LOCALIZATION for row in all_rows)
        failure_total = false_negative + localization
        failure_text = (f"  Failures: target not returned {false_negative}/{failure_total} "
                        f"({_failure_share(false_negative, failure_total)}); box returned but below the overlap bar "
                        f"{localization}/{failure_total} ({_failure_share(localization, failure_total)}).")
        dropout_text = ", ".join("n/a" if rate is None else f"{rate:.3f}" for _, _, rate in bins)
        retention_min = _percentile(retentions, 0)
        retention_median = statistics.median(retentions) if retentions else None
        retention_p10 = _percentile(retentions, 0.1)
        retention_text = ("n/a" if retention_median is None else
                          f"min {retention_min:.1%}, median {retention_median:.1%}, "
                          f"10th percentile {retention_p10:.1%}; at least 90 percent {sum(value >= 0.9 for value in retentions)} of {len(retentions)}")
        sequence_lines.extend([
            f"{sequence['name']}: longest miss run {longest} frames ({longest_seconds:.2f} seconds).",
            f"  Dropout rate in ten equal time bins: {dropout_text}.",
            f"  Recovery after miss runs: {recovery_text}",
            f"  Targets passing every eligible scored frame: {held} of {len(sequence['targets'])}.",
            f"  Target retention: {retention_text}.",
            f"  Retention by condition: {condition_text}.",
            f"  Absolute luminance range: {lum}. Dark is relative to each sequence and means little where the range is narrow.",
            failure_text,
        ])
        request_size = sequence.get("request_frame_size")
        for output_size in sequence.get("output_frame_size", []):
            if request_size and output_size != request_size:
                sequence_lines.append(
                    f"  The service returned boxes at {output_size[0]} by {output_size[1]}; they were scaled "
                    f"to the clip size {request_size[0]} by {request_size[1]} before scoring.")
        if sequence.get("seed_boxes_clamped", 0) > 0:
            sequence_lines.append(f"  Seed boxes clamped inside the frame: {sequence['seed_boxes_clamped']}.")
        total_targets += len(sequence["targets"])
        total_held += held
        total_reliable += sum(value >= 0.9 for value in retentions)
        all_retentions.extend(retentions)
        total_misses += sum(len(item["misses"]) for item in miss_runs)
    median_retention = statistics.median(all_retentions) if all_retentions else None
    median_text = "n/a" if median_retention is None else f"{median_retention:.1%}"
    headline = (f"{total_reliable} of {total_targets} tracked people were followed correctly on at least "
                f"90 percent of their scored frames; the median person was followed on {median_text}. "
                f"There were {total_misses} failed scored frames.")
    return "\n".join([headline, "", *sequence_lines,
                       "", "Frames from the same track are strongly correlated, so intervals from this report overstate certainty.",
                       "MOT20 human boxes cover the whole person including hidden parts, while SAM boxes cover what it sees.",
                       "Low scores on frames tagged occluded may reflect that labelling convention and not a model loss.",
                       "Results apply only to the selected clips and seeded tracks."])


def temporal_report(runs_dir: Path, run_id: str) -> str:
    return render_temporal_report(runs_dir, run_id)
