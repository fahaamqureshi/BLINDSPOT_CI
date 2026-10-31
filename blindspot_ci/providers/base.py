from __future__ import annotations

from typing import Protocol

from blindspot_ci.models import ProviderResult, Scenario


class VisionProvider(Protocol):
    name: str
    model: str

    def inspect(self, scenario: Scenario, probe: str) -> ProviderResult:
        """Return detections for one scenario/probe without owning evaluation or ground truth."""
