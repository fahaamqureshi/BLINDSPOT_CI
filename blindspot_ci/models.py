from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GroundTruthObject(BaseModel):
    label: str
    severity: Literal["low", "medium", "high"] = "medium"


class Scenario(BaseModel):
    id: str
    description: str
    image_url: str | None = None
    probe_catalog: list[str] = Field(min_length=1)
    ground_truth: list[GroundTruthObject]


class Detection(BaseModel):
    label: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)  # None: API gave no score
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResult(BaseModel):
    provider: str
    model: str
    detections: list[Detection] = Field(default_factory=list)
    raw_text: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    cache_hit: bool = False
    parser_status: str = "structured"
    parser_notes: list[str] = Field(default_factory=list)


class ClassMetric(BaseModel):
    label: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    severity: str


class Evaluation(BaseModel):
    metrics: list[ClassMetric]
    blind_spots: list[ClassMetric]
    false_positives: list[ClassMetric]
    weighted_risk: float


class RunReport(BaseModel):
    run_id: str
    scenario_id: str
    provider: str
    status: Literal["complete", "needs_human_review", "blocked"]
    iterations: int
    calls: int
    estimated_cost_usd: float
    probes: list[str]
    results: list[ProviderResult]
    evaluation: Evaluation
    review_reasons: list[str] = Field(default_factory=list)
    planner: str = "heuristic"
    planner_note: str = ""
    skipped_probes: list[str] = Field(default_factory=list)
