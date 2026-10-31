from __future__ import annotations

import json
from pathlib import Path

from blindspot_ci.models import GroundTruthObject, Scenario

ROOT = Path(__file__).resolve().parents[1]


def load_scenarios(path: Path | None = None) -> dict[str, Scenario]:
    source = path or ROOT / "data" / "scenarios.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    truth_path = ROOT / "fixtures" / "ground_truth.json"
    ground_truth = json.loads(truth_path.read_text(encoding="utf-8"))
    scenarios: dict[str, Scenario] = {}
    for item in raw:
        scenario = {**item, "ground_truth": ground_truth.get(item["id"], [])}
        scenarios[item["id"]] = Scenario.model_validate(scenario)
    return scenarios


def parse_truth(spec: str) -> list[GroundTruthObject]:
    """Parse 'person=4,bus=1:high' into ground-truth objects. Count defaults to 1, severity to medium.

    The truth must come from a person who looked at the image, never from the model under test.
    """
    objects: list[GroundTruthObject] = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        label, _, rest = part.partition("=")
        count_text, _, severity = (rest or "1").partition(":")
        label, severity = label.strip(), (severity.strip() or "medium")
        if not label or not count_text.strip().isdigit() or severity not in {"low", "medium", "high"}:
            raise ValueError(f"bad truth entry '{part}'. Use label=count or label=count:severity")
        objects.extend(GroundTruthObject(label=label, severity=severity) for _ in range(int(count_text)))
    if not objects:
        raise ValueError("truth is empty. Example: person=4,bus=1:high")
    return objects


def build_custom_scenario(image_url: str, probes: list[str], truth_spec: str,
                          scenario_id: str = "live_custom") -> Scenario:
    if not probes:
        raise ValueError("give at least one probe")
    return Scenario(id=scenario_id, description="User-supplied image with human-verified ground truth.",
                    image_url=image_url, probe_catalog=probes, ground_truth=parse_truth(truth_spec))
