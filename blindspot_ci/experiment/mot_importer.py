"""Import human-labelled MOT20 tracks into a long-video manifest.

The labels in MOT20 are human annotations. This module never selects a target from a model
output and never downloads image data. The fetch script writes the optional luminance samples
used for the dark condition.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import math
import statistics
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

LABELS_URL = "https://motchallenge.net/data/MOT20Labels.zip"
IMAGE_URL = "https://motchallenge.net/data/MOT20.zip"
LICENSE_TEXT = (
    "MOT20 is published under the Creative Commons Attribution-NonCommercial-ShareAlike 3.0 "
    "License (CC BY-NC-SA 3.0). Non-commercial use only. Do not redistribute the dataset."
)
SEQUENCES = ("MOT20-02", "MOT20-03", "MOT20-05")
OFFICIAL_FRAME_COUNTS = {"MOT20-02": 2782, "MOT20-03": 2405, "MOT20-05": 3315}
OFFICIAL_MP4_URLS = {
    sequence: f"https://motchallenge.net/sequenceVideos/{sequence}-raw.mp4" for sequence in SEQUENCES
}
OFFICIAL_SIZES = {
    "MOT20-02": (1920, 1080),
    "MOT20-03": (1173, 880),
    "MOT20-05": (1654, 1080),
}
OFFICIAL_FPS = {sequence: 25 for sequence in SEQUENCES}


def _safe_member(name: str) -> None:
    """Reject archive names that could escape an extraction root."""
    if not name or "\x00" in name or "\\" in name:
        raise ValueError(f"unsafe archive path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe archive path: {name!r}")
    if ":" in path.parts[0]:
        raise ValueError(f"unsafe archive path: {name!r}")


def _within(root: Path, path: Path) -> Path:
    root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"unsafe path outside labels directory: {path}") from exc
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_seqinfo(text: str) -> dict[str, int]:
    """Parse the numeric fields needed from a MOT ``seqinfo.ini`` file."""
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
        section = parser["Sequence"]
    except (configparser.Error, KeyError) as exc:
        raise ValueError("seqinfo.ini must contain a [Sequence] section") from exc
    fields = {"frameRate": "frameRate", "seqLength": "seqLength", "imWidth": "imWidth", "imHeight": "imHeight"}
    result: dict[str, int] = {}
    for output, key in fields.items():
        try:
            result[output] = int(section[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"seqinfo.ini has no valid integer {key}") from exc
        if result[output] <= 0:
            raise ValueError(f"seqinfo.ini {key} must be positive")
    return result


def _numeric(value: str, label: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"invalid {label}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"invalid {label}: {value!r}")
    return number


def parse_gt(text: str, frame_count: int | None = None) -> dict[int, dict[int, dict[str, Any]]]:
    """Parse MOT rows, retaining only confident pedestrian rows.

    The returned mapping is frame number to track id to a row with an xyxy box. Duplicate
    pedestrian rows for one frame and track are rejected because they make scoring ambiguous.
    """
    rows: dict[int, dict[int, dict[str, Any]]] = {}
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 9:
            raise ValueError(f"gt.txt line {line_number} needs at least 9 comma-separated fields")
        try:
            frame = int(fields[0])
            track_id = int(fields[1])
            flag = int(fields[6])
            class_id = int(fields[7])
        except ValueError as exc:
            raise ValueError(f"gt.txt line {line_number} has invalid integer fields") from exc
        if frame < 1 or track_id < 1:
            raise ValueError(f"gt.txt line {line_number} has an invalid frame or track id")
        if frame_count is not None and frame > frame_count:
            raise ValueError(f"gt.txt line {line_number} exceeds frame count {frame_count}")
        x = _numeric(fields[2], "x")
        y = _numeric(fields[3], "y")
        width = _numeric(fields[4], "width")
        height = _numeric(fields[5], "height")
        visibility = _numeric(fields[8], "visibility")
        if width <= 0 or height <= 0 or not 0 <= visibility <= 1:
            raise ValueError(f"gt.txt line {line_number} has an invalid box or visibility")
        if flag != 1 or class_id != 1:
            continue
        frame_rows = rows.setdefault(frame, {})
        if track_id in frame_rows:
            raise ValueError(f"duplicate pedestrian row for frame {frame}, track {track_id}")
        frame_rows[track_id] = {
            "box": [x, y, x + width, y + height],
            "visibility": visibility,
        }
    return rows


def _track_rows(rows: dict[int, dict[int, dict[str, Any]]]) -> dict[int, list[tuple[int, dict[str, Any]]]]:
    tracks: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for frame in sorted(rows):
        for track_id, row in sorted(rows[frame].items()):
            tracks.setdefault(track_id, []).append((frame, row))
    return tracks


def _quartile_ranks(values: dict[int, float]) -> dict[int, int]:
    ordered = sorted(values, key=lambda track_id: (values[track_id], track_id))
    size = len(ordered)
    return {track_id: min(3, index * 4 // size) for index, track_id in enumerate(ordered)}


def _inside(box: list[float], width: int, height: int) -> bool:
    return 0 <= box[0] and 0 <= box[1] and box[2] <= width and box[3] <= height


def select_targets(
    rows: dict[int, dict[int, dict[str, Any]]],
    frame_size: tuple[int, int],
    max_targets: int = 16,
) -> list[dict[str, Any]]:
    """Select deterministic long tracks spread over box-size and visibility quartiles."""
    if max_targets < 1:
        raise ValueError("max_targets must be positive")
    width, height = frame_size
    tracks = _track_rows(rows)
    candidates: list[tuple[int, list[tuple[int, dict[str, Any]]], int]] = []
    for track_id, track in tracks.items():
        if len(track) < 300:
            continue
        seed = next(
            (frame for frame, row in track if row["visibility"] >= 0.5 and _inside(row["box"], width, height)),
            None,
        )
        if seed is not None:
            candidates.append((track_id, track, seed))
    if not candidates:
        return []

    areas = {
        track_id: statistics.median(
            (row["box"][2] - row["box"][0]) * (row["box"][3] - row["box"][1]) / (width * height)
            for _, row in track
        )
        for track_id, track, _ in candidates
    }
    visibilities = {
        track_id: statistics.median(row["visibility"] for _, row in track)
        for track_id, track, _ in candidates
    }
    area_quartile = _quartile_ranks(areas)
    visibility_quartile = _quartile_ranks(visibilities)
    bins: dict[tuple[int, int], list[tuple[int, list[tuple[int, dict[str, Any]]], int]]] = {}
    for candidate in candidates:
        track_id = candidate[0]
        bins.setdefault((area_quartile[track_id], visibility_quartile[track_id]), []).append(candidate)
    for bucket in bins.values():
        bucket.sort(key=lambda item: item[0])

    selected: list[tuple[int, list[tuple[int, dict[str, Any]]], int]] = []
    for offset in range(max(len(bucket) for bucket in bins.values())):
        for bucket_key in sorted(bins):
            bucket = bins[bucket_key]
            if offset < len(bucket) and len(selected) < max_targets:
                selected.append(bucket[offset])
        if len(selected) == max_targets:
            break
    selected.sort(key=lambda item: item[0])
    return [
        {
            "track_id": track_id,
            "labeled_frames": len(track),
            "seed_frame": seed,
            "seed_box": next(row["box"] for frame, row in track if frame == seed),
            "area_quartile": area_quartile[track_id],
            "visibility_quartile": visibility_quartile[track_id],
            "_rows": track,
        }
        for track_id, track, seed in selected
    ]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile without values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _luminance_info(sequence_info: dict[str, Any]) -> tuple[list[tuple[int, float]], float | None]:
    raw_samples = sequence_info.get("luminance_samples", sequence_info.get("samples", []))
    samples: list[tuple[int, float]] = []
    for sample in raw_samples or []:
        try:
            frame = int(sample["frame"])
            value = float(sample["mean_luminance"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid luminance sample") from exc
        if frame < 1 or not math.isfinite(value) or not 0 <= value <= 255:
            raise ValueError("invalid luminance sample")
        samples.append((frame, value))
    samples.sort()
    if not samples:
        return [], None
    return samples, _percentile([value for _, value in samples], 0.25)


def _tags(
    box: list[float],
    visibility: float,
    frame_size: tuple[int, int],
    frame: int,
    samples: list[tuple[int, float]],
    dark_threshold: float | None,
) -> list[str]:
    width, height = frame_size
    area = (box[2] - box[0]) * (box[3] - box[1])
    tags: list[str] = []
    if visibility < 0.5:
        tags.append("occluded")
    if area < width * height * 0.01:
        tags.append("small_object")
    if box[0] <= 0 or box[1] <= 0 or box[2] >= width or box[3] >= height:
        tags.append("truncated")
    if not samples:
        tags.append("dark:UNVERIFIED")
    else:
        nearest = min(samples, key=lambda item: (abs(item[0] - frame), item[0]))
        if nearest[1] < dark_threshold:
            tags.append("dark")
    return tags or ["normal"]


def _read_preflight(source: Path | dict[str, Any] | None) -> dict[str, Any]:
    if source is None:
        return {}
    if isinstance(source, dict):
        return source
    return json.loads(source.read_text(encoding="utf-8"))


def _sequence_preflight(preflight: dict[str, Any], sequence: str) -> dict[str, Any]:
    values = preflight.get("sequences", {})
    if isinstance(values, list):
        values = {item["name"]: item for item in values if isinstance(item, dict) and item.get("name")}
    return dict(values.get(sequence, {}))


def _member_for(z: zipfile.ZipFile, sequence: str, suffix: str) -> str:
    matches = [name for name in z.namelist() if name.rstrip("/").endswith(f"/{sequence}/{suffix}")]
    if len(matches) != 1:
        raise ValueError(f"labels archive must contain exactly one {sequence}/{suffix}")
    return matches[0]


def _directory_sequence_root(root: Path, sequence: str) -> Path:
    candidates = [root / "MOT20" / "train" / sequence, root / "train" / sequence, root / sequence]
    for candidate in candidates:
        resolved = _within(root, candidate)
        if resolved.is_dir():
            return resolved
    raise ValueError(f"labels directory has no {sequence} sequence")


def _label_texts(source: Path, sequence_names: Iterable[str]) -> tuple[dict[str, tuple[str, str]], str | None]:
    names = list(sequence_names)
    if source.is_file():
        if source.suffix.lower() != ".zip":
            raise ValueError("labels file must be a ZIP archive")
        digest = _sha256(source)
        with zipfile.ZipFile(source) as archive:
            for name in archive.namelist():
                _safe_member(name)
            result = {
                sequence: (
                    archive.read(_member_for(archive, sequence, "gt/gt.txt")).decode("utf-8"),
                    archive.read(_member_for(archive, sequence, "seqinfo.ini")).decode("utf-8"),
                )
                for sequence in names
            }
        return result, digest
    if not source.is_dir():
        raise ValueError(f"labels source does not exist: {source}")
    root = source.resolve()
    result = {}
    for sequence in names:
        sequence_root = _directory_sequence_root(root, sequence)
        gt = _within(root, sequence_root / "gt" / "gt.txt")
        seqinfo = _within(root, sequence_root / "seqinfo.ini")
        if not gt.is_file() or not seqinfo.is_file():
            raise ValueError(f"labels directory is missing files for {sequence}")
        result[sequence] = (gt.read_text(encoding="utf-8"), seqinfo.read_text(encoding="utf-8"))
    return result, None


def _frame_box(row: dict[str, Any]) -> list[float]:
    return [round(float(value), 6) for value in row["box"]]


def build_manifest(
    labels: Path,
    preflight: Path | dict[str, Any] | None = None,
    output: Path | None = None,
    sequences: Iterable[str] = SEQUENCES,
    max_targets: int = 16,
) -> dict[str, Any]:
    """Build and optionally write a MOT20 manifest from a labels archive or extracted directory."""
    sequence_names = tuple(sequences)
    if not sequence_names:
        raise ValueError("at least one sequence is required")
    preflight_data = _read_preflight(preflight)
    label_texts, archive_sha = _label_texts(labels, sequence_names)
    expected_sha = preflight_data.get("labels_archive_sha256")
    if expected_sha and archive_sha and expected_sha != archive_sha:
        raise ValueError("labels archive sha256 does not match preflight")
    sequence_manifests: list[dict[str, Any]] = []
    for sequence in sequence_names:
        info = parse_seqinfo(label_texts[sequence][1])
        sequence_preflight = _sequence_preflight(preflight_data, sequence)
        expected_count = sequence_preflight.get("frame_count", OFFICIAL_FRAME_COUNTS.get(sequence))
        if expected_count is not None and info["seqLength"] != int(expected_count):
            raise ValueError(f"{sequence}: wrong frame count {info['seqLength']}, expected {expected_count}")
        expected_size = sequence_preflight.get("frame_size", OFFICIAL_SIZES.get(sequence))
        actual_size = (info["imWidth"], info["imHeight"])
        if expected_size is not None and tuple(expected_size) != actual_size:
            raise ValueError(f"{sequence}: wrong frame size {actual_size}, expected {tuple(expected_size)}")
        expected_fps = sequence_preflight.get("fps", OFFICIAL_FPS.get(sequence))
        if expected_fps is not None and info["frameRate"] != int(expected_fps):
            raise ValueError(f"{sequence}: wrong fps {info['frameRate']}, expected {expected_fps}")
        rows = parse_gt(label_texts[sequence][0], info["seqLength"])
        selected = select_targets(rows, actual_size, max_targets=max_targets)
        samples, dark_threshold = _luminance_info(sequence_preflight)
        targets: list[dict[str, Any]] = []
        for target in selected:
            seed_frame = target["seed_frame"]
            frames: list[dict[str, Any]] = []
            row_by_frame = {frame: row for frame, row in target.pop("_rows")}
            for frame in range(seed_frame + 1, info["seqLength"] + 1):
                row = row_by_frame.get(frame)
                if row is None or row["visibility"] <= 0.2:
                    frames.append({"frame": frame - 1, "source_frame": frame,
                                   "status": "NOT_SCORED", "box": None,
                                   "visibility": None if row is None else row["visibility"],
                                   "tags": ["NOT_SCORED"]})
                else:
                    frames.append({"frame": frame - 1, "source_frame": frame,
                                   "status": "SCORED", "box": _frame_box(row),
                                   "visibility": round(row["visibility"], 6),
                                   "tags": _tags(row["box"], row["visibility"], actual_size, frame,
                                                 samples, dark_threshold)})
            seed_box = _frame_box({"box": target["seed_box"]})
            seed_box[2] -= 1
            seed_box[3] -= 1
            targets.append({**target, "seed_frame": seed_frame - 1,
                            "source_seed_frame": seed_frame, "seed_box": seed_box, "frames": frames})
        sequence_manifests.append({
            "name": sequence,
            "source_url": sequence_preflight.get("mp4_url", OFFICIAL_MP4_URLS.get(sequence)),
            "fps": info["frameRate"],
            "frame_size": list(actual_size),
            "frame_count": info["seqLength"],
            "luminance_samples": [
                {"frame": frame - 1, "source_frame": frame,
                 "mean_luminance": round(value, 6)} for frame, value in samples
            ],
            "luminance_verified": bool(samples),
            "targets": targets,
        })
    manifest = {
        "dataset": "MOT20",
        "frame_index_base": 0, "source_frame_index_base": 1,
        "seed_frames_scored": False, "min_scored_visibility": 0.2,
        "image_archive_url": preflight_data.get("image_archive_url", IMAGE_URL),
        "labels_archive_url": preflight_data.get("labels_archive_url", LABELS_URL),
        "labels_archive_sha256": archive_sha or expected_sha,
        "license": LICENSE_TEXT,
        "sequences": sequence_manifests,
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def summarize_manifest(manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    for sequence in manifest["sequences"]:
        counts: dict[str, int] = {}
        scored = 0
        luminances = [sample["mean_luminance"] for sample in sequence["luminance_samples"]]
        for target in sequence["targets"]:
            for frame in target["frames"]:
                if frame["status"] == "SCORED":
                    scored += 1
                for tag in frame["tags"]:
                    counts[tag] = counts.get(tag, 0) + 1
        if luminances:
            spread = f"{min(luminances):.1f}-{max(luminances):.1f}, p25={_percentile(luminances, 0.25):.1f}"
            dark_cut = _percentile(luminances, 1 / 3)
            bright_cut = _percentile(luminances, 2 / 3)
            both_thirds = min(luminances) <= dark_cut and max(luminances) >= bright_cut
        else:
            spread, both_thirds = "UNVERIFIED", False
        lines.append(
            f"{sequence['name']}: targets={len(sequence['targets'])} scored_frames={scored} "
            f"tag_counts={counts} luminance_spread={spread} both_bright_and_dark_thirds={both_thirds}"
        )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import MOT20 labels into a long-video manifest")
    parser.add_argument("--labels", type=Path, required=True, help="MOT20Labels.zip or extracted labels directory")
    parser.add_argument("--preflight", type=Path, help="JSON written by fetch_mot20.py")
    parser.add_argument("--out", type=Path, help="manifest path, default is a fresh system temporary directory")
    parser.add_argument("--sequence", action="append", dest="sequences", choices=SEQUENCES)
    parser.add_argument("--max-targets", type=int, default=16)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.out or Path(tempfile.mkdtemp(prefix="blindspot-mot20-import-")) / "mot20-manifest.json"
    if output.suffix.lower() != ".json":
        output = output / "mot20-manifest.json"
    try:
        manifest = build_manifest(args.labels, args.preflight, output, args.sequences or SEQUENCES, args.max_targets)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {output}")
    print(summarize_manifest(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
