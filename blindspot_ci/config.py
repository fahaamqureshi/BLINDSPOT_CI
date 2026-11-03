from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path

from dotenv import load_dotenv

from blindspot_ci.workspace import default_path

if os.getenv("DOTENV_DISABLED", "").strip().lower() not in {"1", "true", "yes"}:
    load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


class ConfigurationError(ValueError):
    """An actionable configuration error without echoing user-provided values."""


def _number(name: str, default: str, kind):
    try:
        return kind(_env(name, default))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a valid {kind.__name__}.") from exc


def _boolean(name: str, default: str) -> bool:
    value = _env(name, default).strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ConfigurationError(f"{name} must be true or false (1 or 0 also accepted).")
    return value in {"true", "1"}


@dataclass(frozen=True)
class Settings:
    """Read from the environment each time Settings() is created, so tests can override it."""

    provider: str = field(default_factory=lambda: _env("BLINDSPOT_PROVIDER", "mock"))
    planner: str = field(default_factory=lambda: _env("BLINDSPOT_PLANNER", "heuristic"))
    model_api_key: str | None = field(default_factory=lambda: os.getenv("MODEL_API_KEY") or None, repr=False)
    meta_base_url: str = field(default_factory=lambda: _env("META_BASE_URL", "https://api.meta.ai/v1"))
    text_model: str = field(default_factory=lambda: _env("META_TEXT_MODEL", "muse-spark-1.3"))
    sam_model: str = field(default_factory=lambda: _env("META_SAM_MODEL", "sam-3.1"))
    image_model: str = field(default_factory=lambda: _env("META_IMAGE_MODEL", "muse-image-1.0"))
    voice_model: str = field(default_factory=lambda: _env("META_VOICE_MODEL", "muse-voice-transcribe-1.0"))
    wonder_model: str = field(default_factory=lambda: _env("META_WONDER_MODEL", "muse-wonder-1.0"))
    sam_stream: bool = field(default_factory=lambda: _boolean("BLINDSPOT_SAM_STREAM", "1"))
    dataset: str = field(default_factory=lambda: _env("BLINDSPOT_DATASET", "synthetic"))
    live_api_enabled: bool = field(default_factory=lambda: _boolean("LIVE_API_ENABLED", "false"))
    min_iou: float = field(default_factory=lambda: _number("BLINDSPOT_MIN_IOU", "0.35", float))
    runs_dir: Path = field(default_factory=lambda: Path(os.getenv("BLINDSPOT_RUNS_DIR") or default_path("artifacts/runs")))
    max_iterations: int = field(default_factory=lambda: _number("BLINDSPOT_MAX_ITERATIONS", "4", int))
    max_calls: int = field(default_factory=lambda: _number("BLINDSPOT_MAX_CALLS", "16", int))
    budget_usd: float = field(default_factory=lambda: _number("BLINDSPOT_BUDGET_USD", "5.00", float))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("BLINDSPOT_CACHE_DIR") or default_path(".blindspot-cache")))
    provenance_path: Path = field(
        default_factory=lambda: Path(os.getenv("BLINDSPOT_PROVENANCE_PATH") or default_path("artifacts/provenance.jsonl")))

    def __post_init__(self) -> None:
        if self.provider not in {"mock", "meta"}:
            raise ConfigurationError("BLINDSPOT_PROVIDER must be mock or meta.")
        if self.planner not in {"heuristic", "mock", "muse"}:
            raise ConfigurationError("BLINDSPOT_PLANNER must be heuristic, mock or muse.")
        if not isfinite(self.min_iou) or not 0 <= self.min_iou <= 1:
            raise ConfigurationError("BLINDSPOT_MIN_IOU must be finite and between 0 and 1.")
        if self.max_iterations < 1 or self.max_calls < 0:
            raise ConfigurationError("BLINDSPOT_MAX_ITERATIONS must be positive; BLINDSPOT_MAX_CALLS must be nonnegative.")
        if not isfinite(self.budget_usd) or self.budget_usd < 0:
            raise ConfigurationError("BLINDSPOT_BUDGET_USD must be finite and nonnegative.")
