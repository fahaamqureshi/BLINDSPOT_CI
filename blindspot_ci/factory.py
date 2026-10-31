from __future__ import annotations

from blindspot_ci.agent import BlindspotAgent
from blindspot_ci.budget import BudgetGuard
from blindspot_ci.cache import JsonCache
from blindspot_ci.config import Settings
from blindspot_ci.experiment.cases import load_named_dataset
from blindspot_ci.experiment.planners import CasePlanner, MockToolPlanner, MuseToolPlanner
from blindspot_ci.experiment.runner import ExperimentRunner
from blindspot_ci.planner import HeuristicPlanner, MusePlanner, ProbePlanner
from blindspot_ci.provenance import ProvenanceLog
from blindspot_ci.providers import MetaMuseSparkAdapter, MetaSam31Adapter, MockVisionProvider
from blindspot_ci.providers.meta_extras import MuseImageAdapter, MuseVoiceAdapter, MuseWonderAuditor


def _live_cfg(settings: Settings | None) -> Settings:
    cfg = settings or Settings()
    if not cfg.live_api_enabled:
        raise PermissionError("Live Meta calls are off. Set LIVE_API_ENABLED=true to allow them.")
    if not cfg.model_api_key:
        raise PermissionError("MODEL_API_KEY is not set.")
    return cfg


def build_image_adapter(settings: Settings | None = None) -> MuseImageAdapter:
    cfg = _live_cfg(settings)
    adapter = MuseImageAdapter(cfg.model_api_key or "", cfg.meta_base_url)
    adapter.model = cfg.image_model
    return adapter


def build_voice_adapter(settings: Settings | None = None) -> MuseVoiceAdapter:
    cfg = _live_cfg(settings)
    adapter = MuseVoiceAdapter(cfg.model_api_key or "", cfg.meta_base_url)
    adapter.model = cfg.voice_model
    return adapter


def build_wonder_auditor(settings: Settings | None = None) -> MuseWonderAuditor:
    cfg = _live_cfg(settings)
    adapter = MuseWonderAuditor(cfg.model_api_key or "", cfg.meta_base_url)
    adapter.model = cfg.wonder_model
    return adapter


def build_agent(settings: Settings | None = None) -> BlindspotAgent:
    cfg = settings or Settings()
    planner: ProbePlanner = HeuristicPlanner()
    if cfg.provider == "meta":
        cfg = _live_cfg(cfg)
        provider = MetaSam31Adapter(cfg.model_api_key or "", cfg.meta_base_url)
        provider.model, provider.stream = cfg.sam_model, cfg.sam_stream
        if cfg.planner == "muse":
            muse = MetaMuseSparkAdapter(cfg.model_api_key or "", cfg.meta_base_url)
            muse.model = cfg.text_model
            planner = MusePlanner(muse)
    else:
        provider = MockVisionProvider()
    return BlindspotAgent(provider, JsonCache(cfg.cache_dir), ProvenanceLog(cfg.provenance_path),
                          cfg.max_iterations, cfg.max_calls, cfg.budget_usd, planner=planner)


def build_experiment(settings: Settings | None = None, planner: str | None = None) -> ExperimentRunner:
    """Case-based experiment. Live calls need BLINDSPOT_PROVIDER=meta AND LIVE_API_ENABLED=true."""
    cfg = settings or Settings()
    dataset = load_named_dataset(cfg.dataset)
    budget = BudgetGuard(max_calls=cfg.max_calls, max_cost_usd=cfg.budget_usd)
    wants_muse = (planner or cfg.planner) == "muse"
    if cfg.provider == "meta" or wants_muse:
        if not cfg.live_api_enabled:
            raise PermissionError("Live Meta calls are off. Set LIVE_API_ENABLED=true to allow them.")
        if not cfg.model_api_key:
            raise PermissionError("MODEL_API_KEY is not set.")
    if cfg.provider == "meta":
        provider = MetaSam31Adapter(cfg.model_api_key or "", cfg.meta_base_url)
        provider.model, provider.stream = cfg.sam_model, cfg.sam_stream
    else:
        provider = MockVisionProvider()
    if wants_muse:
        case_planner: CasePlanner = MuseToolPlanner(cfg.model_api_key or "", cfg.meta_base_url,
                                                    cfg.text_model, budget)
    else:
        case_planner = MockToolPlanner({c.id: c.recovery_case for c in dataset.cases.values()})
    return ExperimentRunner(provider, case_planner, dataset, JsonCache(cfg.cache_dir),
                            ProvenanceLog(cfg.provenance_path), budget, cfg.runs_dir, cfg.min_iou)
