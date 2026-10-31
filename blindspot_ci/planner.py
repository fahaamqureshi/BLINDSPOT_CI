from __future__ import annotations

from typing import Protocol

from blindspot_ci.models import Detection, Scenario

# Generic safety priors for common probe labels. They are domain knowledge, not per-scenario
# ground truth, so the planner stays independent of the evaluation fixtures.
RISK_PRIOR: dict[str, float] = {
    "fire_extinguisher": 4.0,
    "warning_label": 4.0,
    "exit_sign": 4.0,
    "person": 2.0,
    "safety_sign": 2.0,
    "wet_floor": 2.0,
}
DEFAULT_RISK = 1.0
MENTION_BONUS = 1.0


class ProbePlanner(Protocol):
    """Chooses the next probe. It may see scenario metadata and prior observations only."""

    name: str
    estimated_cost_usd: float

    def prepare(self, scenario: Scenario) -> None:
        """Optional one-time setup, for example a single planning call."""

    def next_probe(self, scenario: Scenario, observed: list[Detection], remaining: list[str]) -> str | None:
        """Return one entry of `remaining`, or None to stop."""


def _score(scenario: Scenario, label: str) -> float:
    mentioned = label.replace("_", " ") in scenario.description.lower()
    return RISK_PRIOR.get(label, DEFAULT_RISK) + (MENTION_BONUS if mentioned else 0.0)


class HeuristicPlanner:
    """Deterministic, offline planner: highest prior risk first, ties broken by catalog order.

    Observations are used only to skip a label that was already detected. The ranking itself does
    not depend on them yet, so this is a prioritiser, not an information-gain planner.
    """

    name = "heuristic"
    estimated_cost_usd = 0.0
    status = "heuristic order"

    def prepare(self, scenario: Scenario) -> None:
        return None

    def next_probe(self, scenario: Scenario, observed: list[Detection], remaining: list[str]) -> str | None:
        seen = {d.label for d in observed}
        candidates = [p for p in remaining if p not in seen] or list(remaining)
        if not candidates:
            return None
        order = {p: i for i, p in enumerate(scenario.probe_catalog)}
        return max(candidates, key=lambda p: (_score(scenario, p), -order.get(p, 0)))


class MusePlanner:
    """Uses Muse Spark once per scenario to order probes. It can reorder but never drop probes.

    Any failure falls back to the heuristic order, so a flaky API cannot stop the run.
    """

    name = "muse-spark"
    estimated_cost_usd = 0.0005  # conservative per-call guess; check dashboard usage

    def __init__(self, adapter, fallback: HeuristicPlanner | None = None):
        self.adapter = adapter
        self.fallback = fallback or HeuristicPlanner()
        self._order: list[str] = []
        self.status = "not run"

    def prepare(self, scenario: Scenario) -> None:
        try:
            self._order = list(self.adapter.recommend_probes(scenario))
            self.status = "muse order used: " + ", ".join(self._order)
        except (RuntimeError, ValueError) as exc:  # MetaApiError is a RuntimeError
            self._order = []
            self.status = f"fell back to heuristic: {str(exc)[:120]}"

    def next_probe(self, scenario: Scenario, observed: list[Detection], remaining: list[str]) -> str | None:
        for probe in self._order:
            if probe in remaining:
                return probe
        return self.fallback.next_probe(scenario, observed, remaining)
