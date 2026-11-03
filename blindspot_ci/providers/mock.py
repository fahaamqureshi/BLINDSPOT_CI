from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from blindspot_ci.models import Detection, ProviderResult, Scenario
from blindspot_ci.resources import RESOURCE_ROOT

RESPONSES_PATH = RESOURCE_ROOT / "fixtures" / "mock_responses.json"


def fixtures_digest() -> str:
    """Hash of the scripted answers, so editing them can never replay an old cached answer."""
    import hashlib

    return hashlib.sha256(RESPONSES_PATH.read_bytes()).hexdigest()[:16]


def load_mock_responses(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return json.loads((path or RESPONSES_PATH).read_text(encoding="utf-8"))


class MockVisionProvider:
    """Deterministic provider used for demos and tests; not a model and not a benchmark.

    Canned answers live in fixtures/mock_responses.json. The provider never reads ground truth.
    A probe with no entry means "nothing detected".
    """

    name = "mock"
    model = "mock-sam-3.1-shaped"

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None):
        self.responses = responses if responses is not None else load_mock_responses()

    def inspect(self, scenario: Scenario, probe: str) -> ProviderResult:
        hit = self.responses.get(scenario.id, {}).get(probe)
        detections = []
        if hit:
            metadata = {"note": hit.get("note", "")}
            if "box" in hit:
                metadata["box_xyxy"] = hit["box"]
            detections.append(Detection(label=probe, confidence=hit.get("confidence"), source=self.name,
                                        metadata=metadata))
        return ProviderResult(
            provider=self.name,
            model=self.model,
            detections=detections,
            usage={"input_tokens": 0, "output_tokens": 0},
            estimated_cost_usd=0.0,
        )
