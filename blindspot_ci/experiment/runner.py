"""The experiment loop: planner picks a test, SAM observes, Python scores, planner adapts."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.cache import JsonCache
from blindspot_ci.experiment.cases import (
    Dataset,
    InspectionCase,
    image_path,
    public_case,
    sha256_file,
)
from blindspot_ci.experiment.planners import CasePlanner, PlannerError
from blindspot_ci.experiment.scoring import (
    DEFAULT_MIN_IOU,
    ERROR,
    CaseOutcome,
    score_case,
    summarize,
)
from blindspot_ci.fsutil import atomic_write_text
from blindspot_ci.media import file_to_data_url
from blindspot_ci.models import Detection, ProviderResult, Scenario
from blindspot_ci.provenance import ProvenanceLog, sha256_json
from blindspot_ci.providers.base import VisionProvider
from blindspot_ci.providers.mock import fixtures_digest

RUN_ID = re.compile(r"^[0-9a-f]{16}$")
SAM_CALL_ESTIMATE_USD = 0.0025


def source_label(provider_name: str, cache_hit: bool) -> str:
    """Honest mode label shown with every result: MOCK_FIXTURE, LIVE_META, or a CACHE_ version."""
    base = "LIVE_META" if provider_name == "meta" else "MOCK_FIXTURE"
    return f"CACHE_{base}" if cache_hit else base


def boxes_of(detections: list[Detection]) -> list[tuple[int, int, int, int]]:
    return [tuple(int(v) for v in d.metadata["box_xyxy"]) for d in detections if "box_xyxy" in d.metadata]


def _detection_view(detection: Detection) -> dict[str, Any]:
    return {"bbox": detection.metadata.get("box_xyxy"), "confidence": detection.confidence,
            "mask": detection.metadata.get("mask")}


class ExperimentRunner:
    def __init__(self, provider: VisionProvider, planner: CasePlanner, dataset: Dataset, cache: JsonCache,
                 provenance: ProvenanceLog, budget: BudgetGuard, runs_dir: Path,
                 min_iou: float = DEFAULT_MIN_IOU):
        self.provider, self.planner, self.dataset = provider, planner, dataset
        self.cache, self.provenance, self.budget = cache, provenance, budget
        self.runs_dir, self.min_iou = runs_dir, min_iou

    def run(self, max_steps: int = 5) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:16]
        started = datetime.now(timezone.utc).isoformat()
        cases = self.dataset.cases
        public = {cid: public_case(c) for cid, c in cases.items()}
        remaining = list(cases)
        history: list[dict[str, Any]] = []
        outcomes: list[CaseOutcome] = []
        steps: list[dict[str, Any]] = []
        errors: list[str] = []
        stop_reason, stop_detail = "step_limit_reached", "The configured test limit was reached."
        for _ in range(max_steps):
            if not remaining:
                stop_reason, stop_detail = "suite_complete", "Every configured case was tested."
                break
            try:
                decision = self.planner.choose(public, remaining, history)
            except (PlannerError, BudgetExceeded, RuntimeError, ValueError) as exc:
                errors.append(f"planner stopped the run: {self._clean(exc)}")
                stop_reason, stop_detail = "planner_error", self._clean(exc)
                break
            self.provenance.append({"event": "planner_decision", "run_id": run_id, "planner": decision.planner,
                                    "case_id": decision.case_id, "tool_call_id": decision.tool_call_id})
            if decision.case_id is None:
                stop_reason, stop_detail = "planner_finished", decision.reason
                break
            remaining.remove(decision.case_id)
            case = cases[decision.case_id]
            try:
                step = self._test_case(run_id, case, decision)
            except (BudgetExceeded, RuntimeError, ValueError) as exc:
                message = self._clean(exc)
                errors.append(f"test {case.id} could not run: {message}")
                outcome = CaseOutcome(case.id, ERROR, False, None, message)
                steps.append({"case": public[case.id], "decision": self._decision_view(decision),
                              "outcome": outcome.to_dict(), "prediction": None, "ground_truth": None})
                outcomes.append(outcome)
                stop_reason, stop_detail = "execution_error", message
                break
            steps.append(step)
            outcome = CaseOutcome(**step["outcome"])
            outcomes.append(outcome)
            visible = {k: v for k, v in step["outcome"].items() if k != "case_id"}
            history.append({"case_id": case.id, **visible})
            self.planner.record_result(decision, step["outcome"])
        if not remaining and not errors:
            stop_reason, stop_detail = "suite_complete", "Every configured case was tested."
        report = {
            "id": run_id, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
            "mode": self._run_mode(steps), "provider": self.provider.name,
            "model": self.provider.model, "planner": self.planner.name,
            "planner_prompt_version": getattr(self.planner, "prompt_version", None),
            "dataset": {"id": self.dataset.id, "type": self.dataset.kind,
                        "annotation_status": self.dataset.annotation_status},
            "min_iou": self.min_iou, "steps": steps, "errors": errors,
            "configured_case_ids": sorted(cases),
            "stop_reason": stop_reason, "stop_detail": stop_detail,
            "summary": summarize(outcomes, {cid: c.condition for cid, c in cases.items()}, self.min_iou),
            "calls": self.budget.calls, "estimated_cost_usd": round(self.budget.cost_usd, 6),
        }
        self._save(report)
        self.provenance.append({"event": "run_complete", "run_id": run_id, "report_hash": sha256_json(report)})
        return report

    def _test_case(self, run_id: str, case: InspectionCase, decision: Any) -> dict[str, Any]:
        path = image_path(case)
        digest = sha256_file(path)
        key = f"{self.provider.name}:{self.provider.model}:{digest}:{case.concept}"
        if self.provider.name == "mock":
            key += f":{case.id}:{fixtures_digest()}"  # scripted per case id and per fixture file
        cached = self.cache.get(key)
        started = time.monotonic()
        if cached is not None:
            result = ProviderResult.model_validate(cached)
            result.cache_hit = True
        else:
            live = self.provider.name != "mock"
            self.budget.reserve(SAM_CALL_ESTIMATE_USD if live else 0.0)
            scenario = Scenario(id=case.id, description=case.title, probe_catalog=[case.concept],
                                ground_truth=[], image_url=file_to_data_url(path) if live else None)
            result = self.provider.inspect(scenario, case.concept)
            if result.parser_status != "structured":
                raise RuntimeError(f"provider output was not usable ({result.parser_status}); not scored")
            self.cache.put(key, result.model_dump())
        latency_ms = int((time.monotonic() - started) * 1000)
        outcome = score_case(case, boxes_of(result.detections), self.min_iou)
        source = source_label(self.provider.name, result.cache_hit)
        self.provenance.append({"event": "inference", "run_id": run_id, "case_id": case.id, "source": source,
                                "image_sha256": digest, "status": outcome.status})
        return {"case": public_case(case), "decision": self._decision_view(decision),
                "outcome": outcome.to_dict(),
                "ground_truth": {"visibility": case.visibility, "bbox": case.ground_truth_box,
                                 "label_provenance": case.label_provenance},
                "prediction": {"source": source, "provider": result.provider, "model": result.model,
                               "latency_ms": latency_ms, "parser_status": result.parser_status,
                               "detections": [_detection_view(d) for d in result.detections]},
                "image_sha256": digest}

    @staticmethod
    def _decision_view(decision: Any) -> dict[str, Any]:
        return {"case_id": decision.case_id, "reason": decision.reason, "planner": decision.planner,
                "tool_call_id": decision.tool_call_id}

    def _clean(self, exc: Exception) -> str:
        key = getattr(self.provider, "api_key", None) or getattr(self.planner, "api_key", None)
        text = str(exc)
        return text.replace(key, "[redacted]") if key else text

    def _save(self, report: dict[str, Any]) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.runs_dir / f"{report['id']}.json", json.dumps(report, indent=2))

    def _run_mode(self, steps: list[dict[str, Any]]) -> str:
        """Label the run by what its steps really used, so a fully replayed run never says LIVE."""
        sources = {(s.get("prediction") or {}).get("source") for s in steps} - {None}
        base = source_label(self.provider.name, False)
        if not sources or sources == {base}:
            return base
        if all(x.startswith("CACHE_") for x in sources):
            return f"CACHE_{base}"
        return f"MIXED_CACHED_AND_{base}"


def load_run(runs_dir: Path, run_id: str) -> dict[str, Any]:
    if not RUN_ID.match(run_id):
        raise ValueError("invalid run id")
    path = runs_dir / f"{run_id}.json"
    if not path.is_file():
        raise FileNotFoundError(run_id)
    return json.loads(path.read_text(encoding="utf-8"))
