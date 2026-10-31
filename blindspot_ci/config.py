from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    """Read from the environment each time Settings() is created, so tests can override it."""

    provider: str = field(default_factory=lambda: _env("BLINDSPOT_PROVIDER", "mock"))
    planner: str = field(default_factory=lambda: _env("BLINDSPOT_PLANNER", "heuristic"))
    model_api_key: str | None = field(default_factory=lambda: os.getenv("MODEL_API_KEY") or None)
    meta_base_url: str = field(default_factory=lambda: _env("META_BASE_URL", "https://api.meta.ai/v1"))
    text_model: str = field(default_factory=lambda: _env("META_TEXT_MODEL", "muse-spark-1.3"))
    sam_model: str = field(default_factory=lambda: _env("META_SAM_MODEL", "sam-3.1"))
    image_model: str = field(default_factory=lambda: _env("META_IMAGE_MODEL", "muse-image-1.0"))
    voice_model: str = field(default_factory=lambda: _env("META_VOICE_MODEL", "muse-voice-transcribe-1.0"))
    wonder_model: str = field(default_factory=lambda: _env("META_WONDER_MODEL", "muse-wonder-1.0"))
    sam_stream: bool = field(default_factory=lambda: _env("BLINDSPOT_SAM_STREAM", "1") != "0")
    dataset: str = field(default_factory=lambda: _env("BLINDSPOT_DATASET", "synthetic"))
    live_api_enabled: bool = field(default_factory=lambda: _env("LIVE_API_ENABLED", "false").lower() == "true")
    min_iou: float = field(default_factory=lambda: float(_env("BLINDSPOT_MIN_IOU", "0.35")))
    runs_dir: Path = field(default_factory=lambda: Path(_env("BLINDSPOT_RUNS_DIR", "artifacts/runs")))
    max_iterations: int = field(default_factory=lambda: int(_env("BLINDSPOT_MAX_ITERATIONS", "4")))
    max_calls: int = field(default_factory=lambda: int(_env("BLINDSPOT_MAX_CALLS", "16")))
    budget_usd: float = field(default_factory=lambda: float(_env("BLINDSPOT_BUDGET_USD", "5.00")))
    cache_dir: Path = field(default_factory=lambda: Path(_env("BLINDSPOT_CACHE_DIR", ".blindspot-cache")))
    provenance_path: Path = field(
        default_factory=lambda: Path(_env("BLINDSPOT_PROVENANCE_PATH", "artifacts/provenance.jsonl")))
