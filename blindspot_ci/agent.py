from __future__ import annotations

import uuid

from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.cache import JsonCache
from blindspot_ci.evaluator import evaluate
from blindspot_ci.models import Detection, ProviderResult, RunReport, Scenario
from blindspot_ci.planner import HeuristicPlanner, ProbePlanner
from blindspot_ci.provenance import ProvenanceLog, sha256_json
from blindspot_ci.providers.base import VisionProvider

LIVE_CALL_ESTIMATE_USD = 0.0025  # SAM 3.1 lists $2.50 per 1k images


class BlindspotAgent:
    """Bounded probe loop: plan, reserve budget, inspect, cache, evaluate, gate for review."""

    def __init__(self, provider: VisionProvider, cache: JsonCache, provenance: ProvenanceLog,
                 max_iterations: int = 4, max_calls: int = 12, budget_usd: float = 5.0,
                 planner: ProbePlanner | None = None, budget_parent: BudgetGuard | None = None):
        self.provider, self.cache, self.provenance = provider, cache, provenance
        self.max_iterations = max_iterations
        self.max_calls = max_calls
        self.budget_usd = budget_usd
        self.budget_parent = budget_parent
        self.planner: ProbePlanner = planner or HeuristicPlanner()

    def run(self, scenario: Scenario) -> RunReport:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        budget = BudgetGuard(max_calls=self.max_calls, max_cost_usd=self.budget_usd,
                             parent=self.budget_parent)
        planner = self._prepare_planner(scenario, run_id, budget)
        results: list[ProviderResult] = []
        observed: list[Detection] = []
        probes_run: list[str] = []
        remaining = list(scenario.probe_catalog)
        blocked = False
        failed = False

        while remaining and len(probes_run) < self.max_iterations:
            probe = planner.next_probe(scenario, observed, remaining)
            if probe is None:
                break
            if probe not in remaining:
                # A planner may only pick from the catalog and never repeat a probe.
                self.provenance.append({"event": "planner_invalid", "run_id": run_id, "probe": str(probe)})
                break
            remaining.remove(probe)
            image_ref = sha256_json(scenario.image_url)[:16] if scenario.image_url else "none"
            key = f"{self.provider.name}:{self.provider.model}:{scenario.id}:{image_ref}:{probe}"
            cached = self.cache.get(key)
            if cached is not None:
                result = ProviderResult.model_validate(cached)
                result.cache_hit = True
            else:
                estimate = 0.0 if self.provider.name == "mock" else LIVE_CALL_ESTIMATE_USD
                try:
                    budget.reserve(estimate)
                except BudgetExceeded as exc:
                    self.provenance.append({"event": "budget_blocked", "run_id": run_id, "reason": str(exc)})
                    remaining.append(probe)
                    blocked = True
                    break
                try:
                    result = self.provider.inspect(scenario, probe)
                except (RuntimeError, ValueError) as exc:  # includes MetaApiError
                    self.provenance.append({"event": "provider_error", "run_id": run_id, "probe": probe,
                                            "error": type(exc).__name__})
                    remaining.append(probe)
                    failed = True
                    break
                self.cache.put(key, result.model_dump())
            results.append(result)
            probes_run.append(probe)
            observed.extend(result.detections)
            self.provenance.append({
                "event": "inference",
                "run_id": run_id,
                "scenario_id": scenario.id,
                "probe": probe,
                "planner": planner.name,
                "provider": result.provider,
                "model": result.model,
                "cache_hit": result.cache_hit,
                "input_hash": sha256_json({"scenario": scenario.id, "probe": probe}),
                "parser_status": result.parser_status,
                "usage": result.usage,
                "estimated_cost_usd": result.estimated_cost_usd,
            })

        skipped = [p for p in scenario.probe_catalog if p not in probes_run]
        evaluation = evaluate(scenario.ground_truth, observed)
        reasons: list[str] = []
        if evaluation.blind_spots:
            reasons.append("blind spots require human review before any safety claim")
        if evaluation.false_positives:
            reasons.append("false alarms need human confirmation")
        if any(result.parser_status != "structured" for result in results):
            reasons.append("one or more provider outputs were not parsed into geometry")
        if skipped:
            cause = ("budget or call guard" if blocked else
                     "provider error" if failed else "iteration limit or planner stop")
            reasons.append(f"{len(skipped)} probe(s) not run ({cause}): {', '.join(skipped)}")
        status = "needs_human_review" if reasons else "complete"
        report = RunReport(run_id=run_id, scenario_id=scenario.id, provider=self.provider.name,
                           status=status, iterations=len(results), calls=budget.calls,
                           estimated_cost_usd=budget.cost_usd, probes=probes_run, results=results,
                           evaluation=evaluation, review_reasons=reasons, planner=planner.name,
                           planner_note=getattr(planner, "status", ""),
                           skipped_probes=skipped)
        self.provenance.append({"event": "run_complete", "run_id": run_id,
                                "report_hash": sha256_json(report.model_dump()), "status": status})
        return report

    def _prepare_planner(self, scenario: Scenario, run_id: str, budget: BudgetGuard) -> ProbePlanner:
        """Reserve budget for a paid planner call; fall back to the free heuristic if blocked."""
        planner = self.planner
        if planner.estimated_cost_usd <= 0:
            planner.prepare(scenario)
            return planner
        try:
            budget.reserve(planner.estimated_cost_usd)
        except BudgetExceeded as exc:
            self.provenance.append({"event": "budget_blocked", "run_id": run_id, "reason": f"planner: {exc}"})
            return HeuristicPlanner()
        planner.prepare(scenario)
        self.provenance.append({"event": "planner_call", "run_id": run_id, "planner": planner.name,
                                "estimated_cost_usd": planner.estimated_cost_usd,
                                "planner_status": getattr(planner, "status", "")})
        return planner
