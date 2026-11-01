"""Deterministic cluster bootstrap intervals for repeated video observations."""
from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence
from math import floor
from typing import Any

BOOTSTRAP_SEED = 20260427
BOOTSTRAP_RESAMPLES = 2000
_DAVIS_ID = re.compile(r"^dv_(.+)_f\d+$")
_MOT20_ID = re.compile(r"^(MOT20-\d+)-(\d+)-\d+$")


def group_key(run: dict[str, Any], step: dict[str, Any]) -> str | None:
    """Return an explicit or known video group, and None for independent photos."""
    for container in (step, step.get("case") or {}):
        value = container.get("group")
        if value is not None and str(value):
            return str(value)
    case_id = str((step.get("case") or {}).get("id", ""))
    dataset_id = str((run.get("dataset") or {}).get("id", ""))
    if dataset_id == "davis-2017-frames":
        match = _DAVIS_ID.match(case_id)
        return match.group(1) if match else None
    if dataset_id == "mot20-long":
        match = _MOT20_ID.match(case_id)
        return f"{match.group(1)}-{match.group(2)}" if match else None
    return None


def _percentile(values: Sequence[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = floor(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def cluster_interval(groups: Mapping[str, Sequence[bool]]) -> list[float] | None:
    """Bootstrap a pass-rate interval by resampling complete groups."""
    usable = {str(name): tuple(bool(value) for value in values)
              for name, values in groups.items() if values}
    if len(usable) < 2 or max(map(len, usable.values()), default=0) <= 1:
        return None
    names = sorted(usable)
    rng = random.Random(BOOTSTRAP_SEED)
    rates: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sampled = [usable[rng.choice(names)] for _ in names]
        passed = sum(sum(group) for group in sampled)
        scored = sum(len(group) for group in sampled)
        rates.append(passed / scored)
    rates.sort()
    return [round(_percentile(rates, 0.025), 3), round(_percentile(rates, 0.975), 3)]
