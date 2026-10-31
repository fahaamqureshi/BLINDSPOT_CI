"""Preflight and lightly sample the public MOT20 long-video archives.

Only HTTPS HEAD and byte-range requests are used. The 5 GB image archive is never downloaded in
full. The labels archive is saved under the requested output directory for the importer.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

SEQUENCES = {
    "MOT20-02": {"fps": 25, "frame_size": [1920, 1080], "frame_count": 2782},
    "MOT20-03": {"fps": 25, "frame_size": [1173, 880], "frame_count": 2405},
    "MOT20-05": {"fps": 25, "frame_size": [1654, 1080], "frame_count": 3315},
}
LABELS_URL = "https://motchallenge.net/data/MOT20Labels.zip"
IMAGE_URL = "https://motchallenge.net/data/MOT20.zip"
LICENSE_TEXT = (
    "MOT20 is published under the Creative Commons Attribution-NonCommercial-ShareAlike 3.0 "
    "License (CC BY-NC-SA 3.0). Non-commercial use only. Do not redistribute the dataset."
)


class RangeUnsupported(RuntimeError):
    """The server did not honor a byte range request."""


class ByteLimitExceeded(RuntimeError):
    """The aggregate bytes fetched from one remote file exceeded the hard limit."""


class RangeFile(io.RawIOBase):
    """A seekable remote file that performs each read as one HTTPS range request."""

    def __init__(self, url: str, size: int, max_bytes: int, timeout: int = 30, retries: int = 5):
        if not url.lower().startswith("https://"):
            raise ValueError("only HTTPS URLs are allowed")
        self.url = url
        self.size = size
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.retries = retries
        self.pos = 0
        self.fetched = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        new_pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}.get(whence)
        if new_pos is None or new_pos < 0:
            raise ValueError("invalid remote file seek")
        self.pos = new_pos
        return self.pos

    def read(self, count: int = -1) -> bytes:
        end = self.size if count < 0 else min(self.size, self.pos + count)
        if self.pos >= end:
            return b""
        length = end - self.pos
        if self.fetched + length > self.max_bytes:
            raise ByteLimitExceeded(f"{self.url}: range bytes exceed --max-bytes {self.max_bytes}")
        request = urllib.request.Request(
            self.url, headers={"Range": f"bytes={self.pos}-{end - 1}"}, method="GET"
        )
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    if getattr(response, "status", None) != 206:
                        raise RangeUnsupported(f"{self.url}: server did not return HTTP 206")
                    data = response.read(length)
                break
            except (OSError, urllib.error.HTTPError):
                if attempt == 4:
                    raise
                time.sleep(2 * (attempt + 1))
        if len(data) != length:
            raise RangeUnsupported(f"{self.url}: short range response")
        self.pos = end
        self.fetched += len(data)
        return data

    def readinto(self, buffer: bytearray) -> int:
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def _head(url: str) -> dict[str, Any]:
    if not url.lower().startswith("https://"):
        raise ValueError("only HTTPS URLs are allowed")
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=30) as response:
        length = response.headers.get("Content-Length")
        return {
            "content_length": int(length) if length is not None else None,
            "accept_ranges": response.headers.get("Accept-Ranges", "").lower() == "bytes",
        }


def _range_probe(url: str, size: int, max_bytes: int) -> bool:
    try:
        RangeFile(url, size, max_bytes, timeout=10).read(1)
    except (ByteLimitExceeded, OSError, urllib.error.URLError, urllib.error.HTTPError, RangeUnsupported):
        return False
    return True


def _safe_member(name: str) -> None:
    if not name or "\x00" in name or "\\" in name:
        raise ValueError(f"unsafe archive path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe archive path: {name!r}")
    if ":" in path.parts[0]:
        raise ValueError(f"unsafe archive path: {name!r}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sample_frames(
    archive: zipfile.ZipFile,
    names: list[str],
    sequence: str,
    frame_count: int,
    sample_count: int = 30,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    picks = sorted({round(1 + index * (frame_count - 1) / (sample_count - 1))
                    for index in range(sample_count)})
    by_frame = {}
    for frame in picks:
        suffixes = (f"/{sequence}/img1/{frame:06d}.jpg", f"/{sequence}/img1/{frame:06d}.JPG")
        matches = [name for name in names if name.endswith(suffixes)]
        if len(matches) != 1:
            raise ValueError(f"image archive has no unique image for {sequence} frame {frame}")
        with Image.open(io.BytesIO(archive.read(matches[0]))) as image:
            grayscale = image.convert("L")
            values = list(grayscale.getdata())
            mean = sum(values) / len(values)
            by_frame[frame] = round(mean, 6)
    samples = [{"frame": frame, "mean_luminance": by_frame[frame]} for frame in picks]
    return samples


def _verify_labels_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            _safe_member(name)
        for sequence in SEQUENCES:
            for suffix in (f"/{sequence}/gt/gt.txt", f"/{sequence}/seqinfo.ini"):
                if sum(name.endswith(suffix) for name in names) != 1:
                    raise ValueError(f"labels archive has no unique {sequence}{suffix}")


def _output_dir(value: str | None) -> Path:
    if value is None:
        return Path(tempfile.mkdtemp(prefix="blindspot-mot20-"))
    path = Path(value).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_preflight(
    output: Path,
    max_bytes: int = 200_000_000,
    labels_url: str = LABELS_URL,
    image_url: str = IMAGE_URL,
    sample_count: int = 30,
) -> dict[str, Any]:
    if max_bytes < 1:
        raise ValueError("--max-bytes must be positive")
    if sample_count < 2:
        raise ValueError("--sample-count must be at least 2")
    output.mkdir(parents=True, exist_ok=True)
    labels_head = _head(labels_url)
    image_head = _head(image_url)
    if labels_head["content_length"] is None:
        raise ValueError("labels archive has no Content-Length")
    if labels_head["content_length"] > max_bytes:
        raise ByteLimitExceeded(
            f"labels archive is {labels_head['content_length']} bytes, over --max-bytes {max_bytes}"
        )
    labels_range_ok = _range_probe(labels_url, labels_head["content_length"], max_bytes)
    image_range_ok = bool(image_head["content_length"] and _range_probe(
        image_url, image_head["content_length"], max_bytes
    ))
    if not labels_range_ok:
        raise RangeUnsupported("labels archive is not range-readable")
    labels_reader = RangeFile(labels_url, labels_head["content_length"], max_bytes)
    label_chunks: list[bytes] = []
    while labels_reader.tell() < labels_reader.size:
        label_chunks.append(labels_reader.read(min(2 * 1024 * 1024, labels_reader.size - labels_reader.tell())))
    labels_data = b"".join(label_chunks)
    labels_path = output / "MOT20Labels.zip"
    labels_path.write_bytes(labels_data)
    _verify_labels_archive(labels_path)
    labels_sha256 = _sha256_bytes(labels_data)
    sequence_data: dict[str, dict[str, Any]] = {}
    image_archive = None
    image_names: list[str] = []
    if image_range_ok:
        try:
            image_remote = RangeFile(image_url, image_head["content_length"], max_bytes, timeout=20, retries=1)
            image_archive = zipfile.ZipFile(io.BufferedReader(image_remote, 1 << 16))
            image_names = image_archive.namelist()
            for name in image_names:
                _safe_member(name)
        except (OSError, ValueError, zipfile.BadZipFile, RangeUnsupported, ByteLimitExceeded):
            image_range_ok = False
    for sequence, expected in SEQUENCES.items():
        mp4_url = f"https://motchallenge.net/sequenceVideos/{sequence}-raw.mp4"
        mp4_head = _head(mp4_url)
        mp4_range_ok = bool(mp4_head["content_length"] and _range_probe(
            mp4_url, mp4_head["content_length"], max_bytes
        ))
        samples: list[dict[str, Any]] = []
        sample_error = None
        if image_range_ok and image_archive is not None:
            try:
                samples = _sample_frames(image_archive, image_names, sequence, expected["frame_count"], sample_count)
            except (OSError, ValueError, zipfile.BadZipFile, RangeUnsupported, ByteLimitExceeded) as exc:
                sample_error = str(exc)
        else:
            sample_error = "image archive is not range-readable"
        sequence_data[sequence] = {
            "name": sequence,
            "mp4_url": mp4_url,
            "mp4_content_length": mp4_head["content_length"],
            "mp4_accept_ranges": mp4_range_ok,
            "fps": expected["fps"],
            "frame_size": expected["frame_size"],
            "frame_count": expected["frame_count"],
            "luminance_samples": samples,
            "luminance_verified": bool(samples),
            "luminance_error": sample_error,
        }
        print(
            f"{sequence}: official_mp4={mp4_url} content_length={mp4_head['content_length']} "
            f"accept_ranges={sequence_data[sequence]['mp4_accept_ranges']} fps={expected['fps']} "
            f"frame_size={expected['frame_size'][0]}x{expected['frame_size'][1]} "
            f"frame_count={expected['frame_count']}"
        )
        if samples:
            values = [sample["mean_luminance"] for sample in samples]
            print(f"  luminance: samples={len(samples)} min={min(values):.1f} max={max(values):.1f} verified=True")
        else:
            print(f"  luminance: UNVERIFIED ({sample_error})")
    if image_archive is not None:
        image_archive.close()
    result = {
        "dataset": "MOT20",
        "labels_archive_url": labels_url,
        "labels_archive_path": str(labels_path),
        "labels_archive_content_length": labels_head["content_length"],
            "labels_archive_accept_ranges": labels_range_ok,
        "labels_archive_sha256": labels_sha256,
        "image_archive_url": image_url,
        "image_archive_content_length": image_head["content_length"],
        "image_archive_accept_ranges": image_range_ok,
        "license": LICENSE_TEXT,
        "sequences": sequence_data,
    }
    preflight_path = output / "mot20-preflight.json"
    preflight_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"labels_archive: content_length={labels_head['content_length']} sha256={labels_sha256}")
    print(f"wrote {preflight_path}")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Range-only MOT20 preflight and luminance sampler")
    parser.add_argument("--preflight", action="store_true", help="run the MOT20 preflight")
    parser.add_argument("--out", help="fresh output directory, default is under the system temp directory")
    parser.add_argument("--max-bytes", type=int, default=200_000_000)
    parser.add_argument("--labels-url", default=LABELS_URL)
    parser.add_argument("--image-url", default=IMAGE_URL)
    parser.add_argument("--sample-count", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.preflight:
        print("error: pass --preflight to run the MOT20 preflight", file=sys.stderr)
        return 2
    try:
        run_preflight(_output_dir(args.out), args.max_bytes, args.labels_url, args.image_url, args.sample_count)
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile, RangeUnsupported,
            ByteLimitExceeded) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
