"""Bounded Plan-Act-Observe-Evaluate-Replan loop with validated tools.

The planner only ever receives public case metadata and scored outcomes. Ground
truth stays in the server-side dataset object until evaluate_predictions scores
a stored prediction with the existing plain Python scorer. This module reuses
public_case, score_case, summarize, compare_runs and load_run; it does not
change scoring, ground truth or the separate release gate.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.cache import JsonCache
from blindspot_ci.experiment.cases import Dataset, image_path, public_case, sha256_file
from blindspot_ci.experiment.planners import STRESS_ORDER
from blindspot_ci.experiment.regression import compare_runs
from blindspot_ci.experiment.runner import boxes_of, load_run, source_label
from blindspot_ci.experiment.scoring import DEFAULT_MIN_IOU, CaseOutcome, score_case, summarize
from blindspot_ci.fsutil import atomic_write_text
from blindspot_ci.media import file_to_data_url
from blindspot_ci.models import ProviderResult, Scenario
from blindspot_ci.provenance import ProvenanceLog, sha256_json
from blindspot_ci.providers.base import VisionProvider
from blindspot_ci.providers.mock import fixtures_digest

SAM_CALL_ESTIMATE_USD = 0.0025
HARD_CONDITIONS = ("low_light", "occlusion", "small_object", "truncated", "angle", "absent")
EVIDENCE_TYPES = ("alternate_view", "closer_view", "different_condition", "human_label_check")
_SECRET_KEY = re.compile(
    r"(api[_-]?key|access[_-]?token|secret|password|authorization)", re.IGNORECASE)
_SECRET_VALUE = re.compile(
    r"((?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*)\S+", re.IGNORECASE)
_CASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,60}$")
_RUN_ID = re.compile(r"^[0-9a-f]{16}$")


class ToolValidationError(ValueError):
    """Tool name or arguments failed the fixed schema."""


class ToolExecutionError(RuntimeError):
    """A validated tool call was refused by server-side state."""


class ToolBudgetStop(RuntimeError):
    """The provider request cap or budget stopped the loop."""


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [],
            "additionalProperties": False}


def _str(max_len: int = 320, pattern: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "string", "minLength": 1, "maxLength": max_len}
    if pattern:
        out["pattern"] = pattern
    return out


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_available_tests": _schema({
        "condition": _str(60), "concept": _str(80)}),
    "select_test_case": _schema({
        "case_id": _str(60, r"^[A-Za-z0-9_-]{1,60}$"), "reason": _str(),
        "repeat_justification": _str()}, ["case_id", "reason"]),
    "run_vision_inspection": _schema({
        "case_id": _str(60, r"^[A-Za-z0-9_-]{1,60}$")}, ["case_id"]),
    "evaluate_predictions": _schema({
        "case_id": _str(60, r"^[A-Za-z0-9_-]{1,60}$")}, ["case_id"]),
    "get_previous_failures": _schema({
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "run_id": _str(16, r"^[0-9a-f]{16}$")}),
    "compare_experiments": _schema({
        "baseline_run_id": _str(16, r"^[0-9a-f]{16}$"),
        "candidate_run_id": _str(16, r"^[0-9a-f]{16}$")},
        ["baseline_run_id", "candidate_run_id"]),
    "request_additional_evidence": _schema({
        "case_id": _str(60, r"^[A-Za-z0-9_-]{1,60}$"),
        "evidence_type": {"type": "string", "enum": list(EVIDENCE_TYPES), "maxLength": 60},
        "reason": _str()}, ["case_id", "evidence_type", "reason"]),
    "save_regression_case": _schema({
        "case_id": _str(60, r"^[A-Za-z0-9_-]{1,60}$"), "reason": _str()},
        ["case_id", "reason"]),
    "finish_investigation": _schema({"reason": _str(500)}, ["reason"]),
}
TOOL_NAMES = tuple(TOOL_SCHEMAS)


def validate_tool_args(tool: str, args: Any) -> dict[str, Any]:
    """Validate one tool call against its fixed schema. Extra keys are refused."""
    if tool not in TOOL_SCHEMAS:
        raise ToolValidationError(f"unknown tool: {tool}")
    if not isinstance(args, dict):
        raise ToolValidationError(f"{tool} arguments must be an object")
    schema = TOOL_SCHEMAS[tool]
    extra = sorted(set(args) - set(schema["properties"]))
    if extra:
        raise ToolValidationError(f"{tool} got unsupported arguments: {', '.join(extra)}")
    missing = [key for key in schema["required"] if key not in args]
    if missing:
        raise ToolValidationError(f"{tool} missing required arguments: {', '.join(missing)}")
    cleaned: dict[str, Any] = {}
    for key, value in args.items():
        spec = schema["properties"][key]
        if spec.get("type") == "string":
            if not isinstance(value, str) or not value.strip():
                raise ToolValidationError(f"{tool}.{key} must be a non-empty string")
            value = value.strip()
            if len(value) > spec["maxLength"]:
                raise ToolValidationError(f"{tool}.{key} is too long")
            if spec.get("pattern") and not re.match(spec["pattern"], value):
                raise ToolValidationError(f"{tool}.{key} has an invalid format")
            if spec.get("enum") and value not in spec["enum"]:
                raise ToolValidationError(f"{tool}.{key} is not an allowed value")
        elif spec.get("type") == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ToolValidationError(f"{tool}.{key} must be an integer")
            if not spec["minimum"] <= value <= spec["maximum"]:
                raise ToolValidationError(f"{tool}.{key} is out of range")
        cleaned[key] = value
    return cleaned


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Bound and credential-free copy for traces, summaries and persisted reports."""
    if isinstance(value, dict):
        return {str(k): ("[redacted]" if _SECRET_KEY.search(str(k)) else redact(v, secrets))
                for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in list(value)[:40]]
    if isinstance(value, str):
        text = _SECRET_VALUE.sub(r"\1[redacted]", value)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[redacted]")
        return text[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def _contains_hidden_label(value: Any) -> bool:
    hidden = {"ground_truth", "ground_truth_box", "bbox", "visibility", "label_provenance"}
    if isinstance(value, dict):
        return any(str(k) in hidden or _contains_hidden_label(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_hidden_label(item) for item in value)
    return False


class BoundedAgentTools:
    """Server-side tool implementations. Predictions are stored here, never scored by a model."""

    def __init__(self, dataset: Dataset, provider: VisionProvider, cache: JsonCache,
                 budget: BudgetGuard, runs_dir: Path, run_id: str,
                 max_provider_requests: int = 8, min_iou: float = DEFAULT_MIN_IOU,
                 previous_runs: list[dict[str, Any]] | None = None):
        self.dataset, self.provider, self.cache = dataset, provider, cache
        self.budget, self.runs_dir, self.run_id = budget, runs_dir, run_id
        self.max_provider_requests, self.min_iou = max_provider_requests, min_iou
        self.previous_runs = previous_runs or []
        self.public = {cid: public_case(case) for cid, case in dataset.cases.items()}
        self.selected_case_id: str | None = None
        self.predictions: dict[str, dict[str, Any]] = {}
        self.evaluations: dict[str, dict[str, Any]] = {}
        self.evaluation_order: list[str] = []
        self.experiments: list[dict[str, Any]] = []
        self.evidence_requests: list[dict[str, Any]] = []
        self.saved_regressions: list[dict[str, Any]] = []
        self.provider_requests = 0
        self._repeat_allowed: set[str] = set()
        self._fingerprints: dict[str, str] = {}

    # State given to the planner: public metadata and scored outcomes only.
    def planner_state(self, iteration: int, tools_used: list[str]) -> dict[str, Any]:
        evaluated = [self.evaluations[cid] for cid in self.evaluation_order]
        failures = [{"case_id": o["case_id"], "status": o["status"]}
                    for o in evaluated if o["status"].startswith("FAIL")]
        state = {
            "run_id": self.run_id, "iteration": iteration,
            "available_tests": [self.public[cid] for cid in self.public
                                if cid not in self.evaluations],
            "tested_case_ids": list(self.evaluation_order),
            "selected_case_id": self.selected_case_id,
            "inspected_case_ids": sorted(self.predictions),
            "evaluations": evaluated,
            "last_evaluation": evaluated[-1] if evaluated else None,
            "failures": failures,
            "evidence_requested_for": [r["case_id"] for r in self.evidence_requests],
            "saved_regression_case_ids": [r["case_id"] for r in self.saved_regressions],
            "tools_used": list(tools_used),
            "provider_requests": self.provider_requests,
            "max_provider_requests": self.max_provider_requests,
        }
        if _contains_hidden_label(state):
            raise ToolExecutionError("planner state would contain a hidden label")
        return state

    def dispatch(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return getattr(self, tool)(**args)

    def _case(self, case_id: str):
        if not _CASE_ID.match(case_id) or case_id not in self.dataset.cases:
            raise ToolExecutionError(f"unknown case id: {case_id}")
        return self.dataset.cases[case_id]

    def list_available_tests(self, condition: str | None = None,
                             concept: str | None = None) -> dict[str, Any]:
        tests = [dict(case) for case in self.public.values()
                 if (condition is None or case["condition"] == condition)
                 and (concept is None or case["concept"] == concept)]
        return {"tests": tests[:50], "count": len(tests)}

    def select_test_case(self, case_id: str, reason: str,
                         repeat_justification: str | None = None) -> dict[str, Any]:
        self._case(case_id)
        fingerprint = self._fingerprints.get(case_id)
        already = case_id in self.evaluations or case_id in self.predictions
        if already and fingerprint and not repeat_justification:
            raise ToolExecutionError(
                "repeated identical experiment needs repeat_justification")
        if repeat_justification:
            self._repeat_allowed.add(case_id)
        self.selected_case_id = case_id
        return {"selected_case_id": case_id, "case": dict(self.public[case_id]),
                "repeat_justified": bool(repeat_justification)}

    def run_vision_inspection(self, case_id: str) -> dict[str, Any]:
        case = self._case(case_id)
        if self.selected_case_id != case_id:
            raise ToolExecutionError("select_test_case must run before run_vision_inspection")
        if case_id in self.predictions and case_id not in self._repeat_allowed:
            raise ToolExecutionError(
                "repeated identical experiment needs repeat_justification")
        path = image_path(case)
        digest = sha256_file(path)
        fingerprint = f"{self.provider.name}:{self.provider.model}:{digest}:{case.concept}"
        if case_id in self._fingerprints and self._fingerprints[case_id] == fingerprint \
                and case_id not in self._repeat_allowed:
            raise ToolExecutionError(
                "repeated identical experiment needs repeat_justification")
        key = f"{self.provider.name}:{self.provider.model}:{digest}:{case.concept}"
        if self.provider.name == "mock":
            key += f":{case.id}:{fixtures_digest()}"
        cached = self.cache.get(key)
        started = time.monotonic()
        if cached is not None:
            result = ProviderResult.model_validate(cached)
            result.cache_hit = True
        else:
            if self.provider_requests >= self.max_provider_requests:
                raise ToolBudgetStop(
                    f"max_provider_requests reached ({self.max_provider_requests})")
            live = self.provider.name != "mock"
            self.provider_requests += 1
            try:
                self.budget.reserve(SAM_CALL_ESTIMATE_USD if live else 0.0)
            except BudgetExceeded as exc:
                raise ToolBudgetStop(str(exc)) from exc
            scenario = Scenario(id=case.id, description=case.title,
                                probe_catalog=[case.concept], ground_truth=[],
                                image_url=file_to_data_url(path) if live else None)
            try:
                result = self.provider.inspect(scenario, case.concept)
            except (RuntimeError, ValueError) as exc:
                raise ToolExecutionError(f"provider_failure: {type(exc).__name__}") from exc
            if result.parser_status != "structured":
                raise ToolExecutionError(
                    f"provider output was not usable ({result.parser_status}); not scored")
            self.cache.put(key, result.model_dump())
        self._fingerprints[case_id] = fingerprint
        self._repeat_allowed.discard(case_id)
        experiment_id = f"exp-{self.run_id}-{len(self.experiments) + 1:02d}"
        boxes = boxes_of(result.detections)
        record = {"experiment_id": experiment_id, "case_id": case_id,
                  "source": source_label(self.provider.name, result.cache_hit),
                  "provider": result.provider, "model": result.model,
                  "cache_hit": result.cache_hit, "image_sha256": digest,
                  "latency_ms": int((time.monotonic() - started) * 1000),
                  "parser_status": result.parser_status,
                  "detections": [{"bbox": d.metadata.get("box_xyxy"),
                                  "confidence": d.confidence} for d in result.detections]}
        self.predictions[case_id] = {**record, "_boxes": boxes}
        self.experiments.append(record)
        return {"case_id": case_id, "experiment_id": experiment_id,
                "detection_count": len(boxes), "detections": record["detections"],
                "parser_status": result.parser_status, "source": record["source"],
                "cache_hit": result.cache_hit}

    def evaluate_predictions(self, case_id: str) -> dict[str, Any]:
        case = self._case(case_id)
        stored = self.predictions.get(case_id)
        if stored is None:
            raise ToolExecutionError("run_vision_inspection must run before evaluate_predictions")
        outcome = score_case(case, list(stored["_boxes"]), self.min_iou)
        view = outcome.to_dict()
        self.evaluations[case_id] = view
        if case_id not in self.evaluation_order:
            self.evaluation_order.append(case_id)
        if self.selected_case_id == case_id:
            self.selected_case_id = None
        return dict(view)

    def get_previous_failures(self, limit: int = 10,
                              run_id: str | None = None) -> dict[str, Any]:
        runs = self.previous_runs
        if run_id is not None:
            if not _RUN_ID.match(run_id):
                raise ToolExecutionError("invalid run id")
            runs = [load_run(self.runs_dir, run_id)]
        failures: list[dict[str, Any]] = []
        for run in runs:
            for step in run.get("steps", []):
                outcome = step.get("outcome") or {}
                status = str(outcome.get("status", ""))
                if status.startswith("FAIL"):
                    cid = outcome.get("case_id") or (step.get("case") or {}).get("id")
                    failures.append({"run_id": run.get("id"), "case_id": cid, "status": status})
        for outcome in self.evaluations.values():
            if outcome["status"].startswith("FAIL"):
                failures.append({"run_id": self.run_id, "case_id": outcome["case_id"],
                                 "status": outcome["status"]})
        return {"failures": failures[:limit], "count": len(failures)}

    def compare_experiments(self, baseline_run_id: str,
                            candidate_run_id: str) -> dict[str, Any]:
        baseline = load_run(self.runs_dir, baseline_run_id)
        candidate = load_run(self.runs_dir, candidate_run_id)
        # Agent reports use steps.case/outcome; compare_runs reads that same shape.
        result = compare_runs(baseline, candidate)
        return {"baseline_run_id": baseline_run_id, "candidate_run_id": candidate_run_id,
                **result}

    def request_additional_evidence(self, case_id: str, evidence_type: str,
                                    reason: str) -> dict[str, Any]:
        case = self._case(case_id)
        alternates: list[str] = []
        if case.recovery_case and case.recovery_case not in self.evaluations:
            alternates.append(case.recovery_case)
        alternates += [cid for cid, other in self.dataset.cases.items()
                       if cid != case_id and other.concept == case.concept
                       and cid not in self.evaluations and cid not in alternates][:4]
        record = {"case_id": case_id, "evidence_type": evidence_type, "reason": reason,
                  "alternate_case_ids": alternates}
        self.evidence_requests.append(record)
        return {"requested": True, **record}

    def save_regression_case(self, case_id: str, reason: str) -> dict[str, Any]:
        self._case(case_id)
        outcome = self.evaluations.get(case_id)
        if outcome is None or not outcome["status"].startswith("FAIL"):
            raise ToolExecutionError("only a scored FAIL case in this run can be saved")
        if case_id not in [r["case_id"] for r in self.saved_regressions]:
            self.saved_regressions.append({"case_id": case_id, "status": outcome["status"],
                                           "reason": reason})
        return {"saved": True, "case_id": case_id, "status": outcome["status"]}

    def finish_investigation(self, reason: str) -> dict[str, Any]:
        return {"finished": True, "reason": reason}


class ObservationDrivenPlanner:
    """Mock planner whose next tool branches on the latest scored observation."""

    name = "MOCK_OBSERVATION_PLANNER"

    def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        if "list_available_tests" not in state["tools_used"]:
            return {"tool": "list_available_tests", "args": {}}
        selected = state.get("selected_case_id")
        if selected and selected not in state["inspected_case_ids"]:
            return {"tool": "run_vision_inspection", "args": {"case_id": selected}}
        if selected and selected not in [o["case_id"] for o in state["evaluations"]]:
            return {"tool": "evaluate_predictions", "args": {"case_id": selected}}
        last = state.get("last_evaluation")
        available = state.get("available_tests", [])
        if last is None:
            pick = self._baseline(available)
            if pick is None:
                return self._finish(state, "No untested cases remain.")
            return {"tool": "select_test_case", "args": {
                "case_id": pick, "reason": "Start with the clearest baseline view."}}
        status, cid = last["status"], last["case_id"]
        if status.startswith("FAIL"):
            return self._after_failure(state, cid, status, available)
        if status == "UNKNOWN" and cid not in state["evidence_requested_for"]:
            return {"tool": "request_additional_evidence", "args": {
                "case_id": cid, "evidence_type": "human_label_check",
                "reason": f"{cid} could not be scored from this view; ask for a label check."}}
        pick = self._next_stress(available)
        if pick is not None:
            return {"tool": "select_test_case", "args": {
                "case_id": pick,
                "reason": f"Last result was {status}; try the next stress condition."}}
        return self._finish(state, f"All available cases were evaluated; last result was {status}.")

    def _after_failure(self, state, cid, status, available):
        if cid not in state["evidence_requested_for"]:
            return {"tool": "request_additional_evidence", "args": {
                "case_id": cid, "evidence_type": "alternate_view",
                "reason": f"{cid} failed with {status}; request another view before concluding."}}
        hard = self._next_hard(available, failed_case_id=cid)
        if hard is not None:
            return {"tool": "select_test_case", "args": {
                "case_id": hard,
                "reason": f"After {cid} failed ({status}), test another hard case."}}
        if cid not in state["saved_regression_case_ids"]:
            return {"tool": "save_regression_case", "args": {
                "case_id": cid, "reason": f"Preserve {cid} ({status}) as a regression case."}}
        return self._finish(
            state, f"{cid} failed ({status}), evidence was requested, the regression was "
                   "saved, and no untested hard case remains.")

    @staticmethod
    def _baseline(available):
        return next((c["id"] for c in available if c["condition"] == "normal"),
                    available[0]["id"] if available else None)

    @staticmethod
    def _order(available):
        rank = {name: i for i, name in enumerate(STRESS_ORDER)}
        return sorted(available, key=lambda c: rank.get(c["condition"], len(rank)))

    def _next_stress(self, available):
        ordered = self._order(available)
        return ordered[0]["id"] if ordered else None

    def _next_hard(self, available, failed_case_id):
        ordered = self._order([c for c in available if c["id"] != failed_case_id])
        alternate = [c for c in ordered if c["condition"] == "alternate_view"]
        if alternate:
            return alternate[0]["id"]
        hard = [c for c in ordered if c["condition"] in HARD_CONDITIONS]
        return hard[0]["id"] if hard else (ordered[0]["id"] if ordered else None)

    @staticmethod
    def _finish(state, reason):
        return {"tool": "finish_investigation", "args": {"reason": reason}}


class BoundedAgentLoop:
    """Run planner tool calls until finish, cancellation, a cap or a failure."""

    def __init__(self, provider: VisionProvider, dataset: Dataset, cache: JsonCache,
                 provenance: ProvenanceLog, budget: BudgetGuard, runs_dir: Path,
                 planner: Any | None = None, max_iterations: int = 24,
                 max_provider_requests: int = 8, min_iou: float = DEFAULT_MIN_IOU,
                 previous_runs: list[dict[str, Any]] | None = None,
                 should_cancel: Callable[[], bool] | None = None):
        if max_iterations < 1 or max_provider_requests < 0:
            raise ValueError("iteration and provider request caps must be positive bounds")
        self.provider, self.dataset = provider, dataset
        self.cache, self.provenance, self.budget = cache, provenance, budget
        self.runs_dir = runs_dir
        self.planner = planner or ObservationDrivenPlanner()
        self.max_iterations, self.max_provider_requests = max_iterations, max_provider_requests
        self.min_iou, self.previous_runs = min_iou, previous_runs or []
        self.should_cancel = should_cancel

    def _secrets(self) -> tuple[str, ...]:
        found = []
        for obj in (self.provider, self.planner):
            key = getattr(obj, "api_key", None)
            if isinstance(key, str) and key:
                found.append(key)
        return tuple(found)

    def run(self) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:16]
        started = datetime.now(timezone.utc).isoformat()
        secrets = self._secrets()
        tools = BoundedAgentTools(self.dataset, self.provider, self.cache, self.budget,
                                  self.runs_dir, run_id, self.max_provider_requests,
                                  self.min_iou, self.previous_runs)
        trace: list[dict[str, Any]] = []
        tools_used: list[str] = []
        errors: list[str] = []
        finish_reason = "max_iterations_reached"
        iteration = 0
        for iteration in range(1, self.max_iterations + 1):
            if self.should_cancel is not None and self.should_cancel():
                finish_reason = "cancelled_by_user"
                trace.append({"iteration": iteration, "tool": "cancelled_by_user",
                              "args": {}, "observation": {"cancelled": True}})
                break
            state = tools.planner_state(iteration, tools_used)
            try:
                call = self.planner.decide(state)
                tool = call["tool"]
                raw_args = call.get("args", {})
            except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
                # Planner failure must stop the loop, never invent actions.
                finish_reason = f"planner_failure: {type(exc).__name__}"
                errors.append(finish_reason)
                trace.append({"iteration": iteration, "tool": "planner_failure",
                              "args": {}, "observation": {"error": type(exc).__name__}})
                break
            try:
                args = validate_tool_args(tool, raw_args)
            except ToolValidationError as exc:
                finish_reason = f"invalid_tool_args: {exc}"
                errors.append(finish_reason)
                trace.append({"iteration": iteration, "tool": redact(str(tool), secrets),
                              "args": redact(raw_args, secrets),
                              "observation": {"rejected": str(exc)}})
                break
            try:
                observation = tools.dispatch(tool, args)
            except ToolBudgetStop as exc:
                finish_reason = f"budget_or_request_cap: {exc}"
                errors.append(finish_reason)
                trace.append({"iteration": iteration, "tool": tool,
                              "args": redact(args, secrets),
                              "observation": {"stopped": str(exc)}})
                break
            except (ToolExecutionError, BudgetExceeded, FileNotFoundError, ValueError) as exc:
                finish_reason = f"tool_rejected: {exc}"
                errors.append(finish_reason)
                trace.append({"iteration": iteration, "tool": tool,
                              "args": redact(args, secrets),
                              "observation": {"rejected": str(exc)}})
                break
            tools_used.append(tool)
            trace.append({"iteration": iteration, "tool": tool, "args": redact(args, secrets),
                          "observation": redact(observation, secrets)})
            self.provenance.append({"event": "agent_tool", "run_id": run_id, "tool": tool,
                                    "iteration": iteration})
            if tool == "finish_investigation":
                finish_reason = str(redact(args["reason"], secrets))
                break
        else:
            iteration = self.max_iterations
        steps = []
        for case_id in tools.evaluation_order:
            stored = tools.predictions[case_id]
            public = dict(tools.public[case_id])
            steps.append({"case": public, "experiment_id": stored["experiment_id"],
                          "outcome": tools.evaluations[case_id],
                          "prediction": {"source": stored["source"],
                                         "provider": stored["provider"],
                                         "model": stored["model"],
                                         "latency_ms": stored["latency_ms"],
                                         "parser_status": stored["parser_status"],
                                         "detections": stored["detections"]},
                          "image_sha256": stored["image_sha256"]})
        outcomes = [CaseOutcome(**tools.evaluations[cid]) for cid in tools.evaluation_order]
        experiment_ids = [item["experiment_id"] for item in tools.experiments]
        failures = [o.case_id for o in outcomes if o.status.startswith("FAIL")]
        final_summary = str(redact(
            f"Run {run_id} finished ({finish_reason}). Experiments: "
            f"{', '.join(experiment_ids) if experiment_ids else 'none'}. "
            f"Evaluated cases: {', '.join(tools.evaluation_order) if tools.evaluation_order else 'none'}. "
            f"Failures: {', '.join(failures) if failures else 'none'}. "
            "Release gate remains a separate fixed-suite audit; this agent did not run, "
            "skip or retune it.", secrets))
        sources = {step["prediction"]["source"] for step in steps}
        base = source_label(self.provider.name, False)
        mode = base if not sources or sources == {base} else (
            f"CACHE_{base}" if all(s.startswith("CACHE_") for s in sources)
            else f"MIXED_CACHED_AND_{base}")
        report = {
            "id": run_id, "run_id": run_id, "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(), "mode": mode,
            "provider": self.provider.name, "model": self.provider.model,
            "planner": getattr(self.planner, "name", type(self.planner).__name__),
            "dataset": {"id": self.dataset.id, "type": self.dataset.kind,
                        "annotation_status": self.dataset.annotation_status},
            "min_iou": self.min_iou, "iterations": iteration,
            "configured_case_ids": sorted(self.dataset.cases),
            "max_iterations": self.max_iterations,
            "max_provider_requests": self.max_provider_requests,
            "provider_requests": tools.provider_requests,
            "calls": self.budget.calls, "estimated_cost_usd": round(self.budget.cost_usd, 6),
            "steps": steps, "trace": trace, "agent_trace": trace, "tools_used": tools_used,
            "tool_inventory": list(TOOL_NAMES), "errors": errors,
            "evidence_requests": tools.evidence_requests,
            "saved_regression_cases": tools.saved_regressions,
            "summary": summarize(outcomes,
                                 {cid: c.condition for cid, c in self.dataset.cases.items()},
                                 self.min_iou),
            "finish_reason": finish_reason, "stop_reason": finish_reason,
            "final_summary": final_summary,
            "release_gate": {"status": "SEPARATE_FIXED_SUITE_REQUIRED",
                             "agent_can_modify": False, "agent_can_skip": False},
        }
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.runs_dir / f"{run_id}.json", json.dumps(report, indent=2))
        self.provenance.append({"event": "agent_run_complete", "run_id": run_id,
                                "experiment_ids": experiment_ids,
                                "report_hash": sha256_json(report),
                                "finish_reason": finish_reason})
        return report
