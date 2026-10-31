from __future__ import annotations

import base64
from pathlib import Path

MAX_IMAGE_BYTES = 4_000_000
MIME_BY_SUFFIX = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
ALLOWED_DATA_PREFIXES = tuple(f"data:{mime};base64," for mime in set(MIME_BY_SUFFIX.values()))


def file_to_data_url(path: str | Path) -> str:
    """Read a local image and return a data: URL, so the API never has to download it.

    This avoids hosts whose robots.txt blocks Meta's fetcher. The image bytes are sent to the API,
    so use only public or authorized images.
    """
    file = Path(path).expanduser()
    if not file.is_file():
        raise ValueError(f"image file not found: {file}")
    mime = MIME_BY_SUFFIX.get(file.suffix.lower())
    if mime is None:
        raise ValueError(f"unsupported image type '{file.suffix}'. Use jpg, png or webp")
    data = file.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"image is {len(data):,} bytes; the limit here is {MAX_IMAGE_BYTES:,}. Resize it first")
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def is_allowed_image_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith("https://") or lowered.startswith(ALLOWED_DATA_PREFIXES)
