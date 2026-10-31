"""Offline replay of test-ordering policies against outcomes saved in a run report."""
from __future__ import annotations

from typing import Any

from blindspot_ci.experiment.baseline import compare_to_random
from blindspot_ci.experiment.planners import CasePlanner, MuseToolPlanner


class ReplayError(ValueError):
    """The saved run cannot be replayed safely or does not contain scored cases."""


def scored_outcomes(run: dict[str, Any]) -> dict[str, str]:
    """Return case statuses that can be scored, excluding UNKNOWN and ERROR outcomes."""
    outcomes: dict[str, str] = {}
    for step in run.get("steps", []):
        outcome = step.get("outcome", {})
        case_id = outcome.get("case_id") or step.get("case", {}).get("id")
        status = outcome.get("status")
        if case_id and (status == "PASS" or (isinstance(status, str) and status.startswith("FAIL_"))):
            outcomes[case_id] = status
    return outcomes


def _replay_cases(run: dict[str, Any], outcomes: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Get planner-visible case metadata from the saved steps, with safe fallbacks."""
    cases: dict[str, dict[str, Any]] = {}
    for step in run.get("steps", []):
        case = step.get("case") or {}
        case_id = case.get("id") or step.get("outcome", {}).get("case_id")
        if case_id in outcomes:
            cases[case_id] = dict(case)
    for case_id in outcomes:
        cases.setdefault(case_id, {"id": case_id, "condition": "unknown"})
    return cases


def replay_outcomes(outcomes: dict[str, str], planner: CasePlanner, steps: int,
                    cases: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Replay a planner on a scored outcome table and compare its order with random selection.

    This evaluates only a test-ordering policy. It never calls an inference or planning API.
    """
    if isinstance(planner, MuseToolPlanner):
        raise ReplayError("MuseToolPlanner is refused in replay because replay must make zero network calls")
    if steps < 1:
        raise ReplayError("steps must be at least 1")

    if not outcomes:
        raise ReplayError("replay needs at least one scored PASS or FAIL_* outcome")
    cases = cases or {case_id: {"id": case_id, "condition": "unknown"} for case_id in outcomes}
    remaining = list(outcomes)
    history: list[dict[str, Any]] = []
    order: list[str] = []
    while remaining and len(order) < steps:
        decision = planner.choose(cases, remaining, history)
        if decision.case_id is None:
            break
        if decision.case_id not in remaining:
            raise ReplayError(f"planner selected an unavailable case during replay: {decision.case_id}")
        remaining.remove(decision.case_id)
        status = outcomes[decision.case_id]
        result = {"case_id": decision.case_id, "status": status, "scoreable": True}
        order.append(decision.case_id)
        history.append(result)
        planner.record_result(decision, result)

    if not order:
        raise ReplayError("planner selected no scored cases during replay")
    comparison = compare_to_random(
        [outcomes[case_id].startswith("FAIL_") for case_id in order],
        len(outcomes),
        sum(status.startswith("FAIL_") for status in outcomes.values()),
    )
    return {
        "policy": planner.name,
        "order": order,
        "comparison": comparison,
        "honesty": ("This replay evaluates a test-ordering policy on saved outcomes, not the model. "
                     + comparison["note"]),
    }


def replay_planner(run: dict[str, Any], planner: CasePlanner, steps: int) -> dict[str, Any]:
    """Replay a planner against the scoreable outcomes in a saved run report."""
    outcomes = scored_outcomes(run)
    return replay_outcomes(outcomes, planner, steps, _replay_cases(run, outcomes))


def replay_run(run: dict[str, Any], planner: CasePlanner, steps: int) -> dict[str, Any]:
    """Compatibility name for callers that describe the input as a saved run."""
    return replay_planner(run, planner, steps)
