from __future__ import annotations

import dataclasses
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from blindspot_ci import factory
from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.config import Settings
from blindspot_ci.data import load_scenarios
from blindspot_ci.experiment import release_gate
from blindspot_ci.experiment.card import build_card
from blindspot_ci.experiment.cases import MANIFESTS, image_path, load_named_dataset, public_case
from blindspot_ci.experiment.corruptions import generate_corruptions
from blindspot_ci.experiment.reviews import add_note, load_extras, save_audit
from blindspot_ci.experiment.runner import RUN_ID, boxes_of, load_run, source_label
from blindspot_ci.experiment.scoring import score_case
from blindspot_ci.experiment.stress import generate_variants, write_manifest
from blindspot_ci.factory import build_agent, build_experiment
from blindspot_ci.models import Scenario
from blindspot_ci.providers.meta import MetaApiError
from blindspot_ci.providers.meta_extras import (
    IMAGE_COST_USD,
    MAX_WAV_BYTES,
    VOICE_CALL_ESTIMATE_USD,
    WONDER_CALL_ESTIMATE_USD,
    MuseVoiceAdapter,
    audit_input,
)
from blindspot_ci.providers.mock import MockVisionProvider
from blindspot_ci.security import install_local_guard

WEB = Path(__file__).parent / "web"
EXAMPLES = Path(__file__).resolve().parent.parent / "fixtures" / "examples"
app = FastAPI(title="BLINDSPOT CI", version="0.1.0")
install_local_guard(app)


class RunRequest(BaseModel):
    scenario_id: str = "warehouse_001"


class ExperimentRequest(BaseModel):
    max_steps: int = Field(default=5, ge=1, le=8)
    dataset: str | None = None


class StressRequest(BaseModel):
    source: str = "real"
    edits: list[str] = Field(min_length=1, max_length=3)
    case_ids: list[str] | None = None


class CorruptRequest(BaseModel):
    source: str = "real"
    corruptions: list[str] = Field(min_length=1, max_length=6)
    severities: list[int] = Field(default=[3], min_length=1, max_length=5)
    case_ids: list[str] | None = None


class NoteRequest(BaseModel):
    case_id: str
    text: str = Field(min_length=1, max_length=1000)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB / "home.html")


@app.get("/app")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/guide")
def guide_page() -> FileResponse:
    return FileResponse(WEB / "guide.html")


@app.get("/demo")
def demo_page() -> RedirectResponse:
    return RedirectResponse("/", status_code=307)


@app.get("/site.css")
def site_css() -> FileResponse:
    return FileResponse(WEB / "site.css", media_type="text/css")


@app.get("/landing.css")
def landing_css() -> FileResponse:
    return FileResponse(WEB / "landing.css", media_type="text/css")


@app.get("/probes")
def probes_page() -> RedirectResponse:
    return RedirectResponse("/", status_code=307)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider": Settings().provider}


def _dataset(name: str | None):
    try:
        return load_named_dataset(name or Settings().dataset)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (KeyError, TypeError) as exc:
        raise HTTPException(422, f"dataset manifest is malformed (missing or wrong field {exc})") from exc


def _available_datasets() -> list[str]:
    return [name for name, path in MANIFESTS.items() if path.is_file()]


_SESSION: BudgetGuard | None = None


def _guard(cfg: Settings) -> BudgetGuard:
    """One spend cap shared by every image, voice and audit call this server makes, so repeated
    clicks cannot exceed BLINDSPOT_BUDGET_USD. Experiments keep their own per-run guard."""
    global _SESSION
    if _SESSION is None:
        _SESSION = BudgetGuard(max_calls=max(cfg.max_calls * 10, 100), max_cost_usd=cfg.budget_usd)
    return _SESSION


def _live(build):
    """Build a live adapter or answer 403 when live calls are off."""
    try:
        return build()
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


def _runs_dir_for(run_id: str) -> Path:
    """Saved runs first; the committed example runs answer when the id is not saved locally. Read only."""
    runs = Settings().runs_dir
    if RUN_ID.match(run_id) and not (runs / f"{run_id}.json").is_file() and (EXAMPLES / f"{run_id}.json").is_file():
        return EXAMPLES
    return runs


def _run_or_404(run_id: str) -> None:
    try:
        load_run(Settings().runs_dir, run_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, "run not found") from exc


MODEL_ROLES = [
    {"model": "Muse Spark 1.3", "role": "Agent: picks each test by function calling when the Muse planner is used", "id": "muse-spark-1.3"},
    {"model": "SAM 3.1", "role": "Segments the photo: boxes and masks", "id": "sam-3.1"},
    {"model": "Muse Image", "role": "Makes labeled stress variants (low light, glare, blur)", "id": "muse-image-1.0"},
    {"model": "Muse Voice Transcribe", "role": "Turns a spoken reviewer note into text", "id": "muse-voice-transcribe-1.0"},
    {"model": "Muse Wonder", "role": "Writes the plain-language audit of a finished run", "id": "muse-wonder-1.0"},
]


@app.get("/api/info")
def info(dataset: str | None = None) -> dict[str, object]:
    cfg = Settings()
    data = _dataset(dataset)
    return {"mode": source_label(cfg.provider, False), "provider": cfg.provider, "planner": cfg.planner,
            "live_enabled": cfg.live_api_enabled, "min_iou": cfg.min_iou,
            "dataset": {"id": data.id, "type": data.kind, "annotation_status": data.annotation_status},
            "datasets": _available_datasets(), "default_dataset": cfg.dataset, "models": MODEL_ROLES}


@app.get("/api/cases")
def cases(dataset: str | None = None) -> dict[str, list[dict[str, object]]]:
    """Test inventory without labels."""
    return {"cases": [public_case(c) for c in _dataset(dataset).cases.values()]}


@app.get("/api/practice-preview")
def practice_preview() -> dict[str, object]:
    """Read-only, offline product example, independent of configured live services."""
    dataset = load_named_dataset("synthetic")
    provider = MockVisionProvider()
    steps = []
    for case in dataset.cases.values():
        scenario = Scenario(id=case.id, description=case.title, probe_catalog=[case.concept],
                            ground_truth=[])
        prediction = provider.inspect(scenario, case.concept)
        outcome = score_case(case, boxes_of(prediction.detections))
        steps.append({"case": public_case(case), "outcome": outcome.to_dict(),
                      "reference_box": case.ground_truth_box,
                      "prediction_boxes": boxes_of(prediction.detections)})
    return {"mode": "MOCK_FIXTURE", "cost_usd": 0, "steps": steps,
            "notice": "Synthetic drawings and scripted answers. Software demonstration only, not model performance."}


@app.get("/api/cases/{case_id}/image")
def case_image(case_id: str, dataset: str | None = None) -> FileResponse:
    case = _dataset(dataset).cases.get(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    try:
        path = image_path(case)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, f"photo for case {case_id} is not in this checkout (its licence is not confirmed "
                                 "for redistribution); the saved results still show the scores")
    return FileResponse(path)


@app.post("/api/experiment")
def experiment(request: ExperimentRequest) -> dict[str, object]:
    cfg = Settings()
    if request.dataset:
        _dataset(request.dataset)
        cfg = dataclasses.replace(cfg, dataset=request.dataset)
    try:
        runner = build_experiment(cfg)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    spends = cfg.provider == "meta" or cfg.planner == "muse"
    if spends and _guard(cfg).exhausted():
        raise HTTPException(429, "this server's spend cap is used up; restart it or raise BLINDSPOT_BUDGET_USD")
    report = runner.run(request.max_steps)
    if report["estimated_cost_usd"] > 0:
        _guard(cfg).charge(report["calls"], report["estimated_cost_usd"])
    return report


@app.get("/api/runs")
def recent_runs(limit: int = Query(default=12, ge=1, le=50)) -> list[dict[str, object]]:
    """Recent local run summaries, without labels, reviewer notes or model output."""
    runs = Settings().runs_dir
    records = []
    for path in runs.glob("*.json"):
        if not RUN_ID.fullmatch(path.stem) or path.is_symlink():
            continue
        try:
            run = load_run(runs, path.stem)
            if not isinstance(run, dict):
                continue
            summary, dataset, steps = run.get("summary"), run.get("dataset"), run.get("steps")
            if not isinstance(summary, dict) or not isinstance(dataset, dict) or not isinstance(steps, list):
                continue
            records.append({"id": path.stem, "dataset": dataset.get("id"),
                            "mode": run.get("mode"), "started_at": str(run.get("started_at", "")),
                            "tests": len(steps), "failed": summary.get("failed", 0)})
        except (ValueError, OSError, TypeError):
            continue
    return sorted(records, key=lambda row: row["started_at"], reverse=True)[:limit]


@app.get("/api/runs/{run_id}")
def run_record(run_id: str) -> dict[str, object]:
    try:
        runs = _runs_dir_for(run_id)
        return {**load_run(runs, run_id), **load_extras(runs, run_id)}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, "run not found") from exc


@app.get("/api/runs/{run_id}/release-gate")
def run_release_gate(run_id: str) -> dict[str, object]:
    try:
        return release_gate.evaluate_file(_runs_dir_for(run_id), run_id, release_gate.load_policy(None))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, "run not found") from exc


EXAMPLE_TITLES = {"coco-val2017": "Everyday photos (COCO), live run",
                  "davis-2017-frames": "Video frames (DAVIS), live run"}


def _headline(gate: dict[str, object]) -> str:
    policy = gate["policy"]
    bar = f"{policy['min_pass_rate']:.2f}"
    conds = gate["conditions"]
    names = [f.split(":")[0] for f in gate["failing"]]
    if not names:
        names = [n for n, c in conds.items() if c["scored"] < policy["min_cases_per_condition"]]
        if not names:
            return str(gate.get("reason") or "no blocking condition found")
        parts = ", ".join(f"{n} {conds[n]['scored']} scored" for n in names)
        return f"{parts}; {policy['min_cases_per_condition']} scored needed per condition"
    return ", ".join(f"{n} {conds[n]['passed']} of {conds[n]['scored']}" for n in names) + f" against a {bar} bar"


@app.get("/api/examples")
def examples() -> list[dict[str, object]]:
    """Committed real runs, summarised by the release gate. Every number comes from the saved file."""
    out: list[dict[str, object]] = []
    policy = release_gate.load_policy(None)
    for path in sorted(EXAMPLES.glob("*.json")) if EXAMPLES.is_dir() else []:
        if not RUN_ID.match(path.stem):
            continue
        try:
            run = load_run(EXAMPLES, path.stem)
            gate = release_gate.evaluate_file(EXAMPLES, path.stem, policy)
        except (ValueError, KeyError, TypeError, OSError):
            continue  # one damaged example file must not take the whole list down
        summary = run.get("summary") or {}
        dataset = run.get("dataset") or {}
        out.append({"id": run["id"], "title": EXAMPLE_TITLES.get(dataset.get("id"), str(dataset.get("id"))),
                    "dataset": dataset.get("id"), "mode": run.get("mode"), "decision": gate["decision"],
                    "headline": _headline(gate), "passed": summary.get("passed"), "scored": summary.get("scored"),
                    "cost_usd": run.get("estimated_cost_usd"), "tests": len(run.get("steps") or [])})
    return out


@app.post("/api/stress")
def stress(request: StressRequest) -> dict[str, object]:
    """Muse Image makes labeled variants of the source dataset. About $0.01 per image."""
    cfg = Settings()
    source = _dataset(request.source)
    if source.kind.startswith("GENERATED"):
        raise HTTPException(422, "variants are made from synthetic or real photos, not from other variants")
    adapter = _live(lambda: factory.build_image_adapter(cfg))
    try:
        entries = generate_variants(source, request.edits, adapter, _guard(cfg), request.case_ids)
    except (ValueError, BudgetExceeded, OSError, MetaApiError) as exc:
        kept = getattr(exc, "partial_entries", [])
        if kept:
            write_manifest(kept, source)  # variants already paid for are kept
        note = f" ({len(kept)} variants already made were kept)" if kept else ""
        raise HTTPException(502 if isinstance(exc, MetaApiError) else 422, str(exc) + note) from exc
    write_manifest(entries, source)
    return {"created": [e["id"] for e in entries], "dataset": "generated",
            "estimated_cost_usd": round(len(entries) * IMAGE_COST_USD, 4),
            "note": "Generated by Muse Image. Boxes are inherited, not re-verified. Check the yellow box."}


@app.post("/api/corrupt")
def corrupt(request: CorruptRequest) -> dict[str, object]:
    """Measured corruptions (no model call, free). Labels stay exact because no pixel moves."""
    source = _dataset(request.source)
    if source.kind.startswith(("GENERATED", "MEASURED")):
        raise HTTPException(422, "corruptions are made from synthetic, real or open photos, not from other variants")
    try:
        entries = generate_corruptions(source, request.corruptions, request.severities, request.case_ids)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    write_manifest(entries, source, name="corrupted")
    return {"created": [e["id"] for e in entries], "dataset": "corrupted", "estimated_cost_usd": 0.0,
            "note": "Deterministic corruptions. Labels are exact. Running them on SAM costs about $0.0025 each."}


@app.get("/api/runs/{run_id}/card", response_class=PlainTextResponse)
def run_card(run_id: str) -> PlainTextResponse:
    """Evaluation card as Markdown, built by Python from the saved run."""
    try:
        runs = _runs_dir_for(run_id)
        run = {**load_run(runs, run_id), **load_extras(runs, run_id)}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, "run not found") from exc
    return PlainTextResponse(build_card(run), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="evaluation-card-{run_id}.md"'})


@app.post("/api/runs/{run_id}/notes")
def add_text_note(run_id: str, request: NoteRequest) -> dict[str, object]:
    _run_or_404(run_id)
    try:
        return add_note(Settings().runs_dir, run_id, request.case_id, request.text, "typed")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/runs/{run_id}/voice")
async def add_voice_note(run_id: str, case_id: str, request: Request) -> dict[str, object]:
    """Raw WAV body (mono PCM, 16 kHz or 24 kHz). Muse Voice Transcribe turns it into a note."""
    _run_or_404(run_id)
    adapter = _live(factory.build_voice_adapter)
    if int(request.headers.get("content-length") or 0) > MAX_WAV_BYTES:
        raise HTTPException(413, "audio is over 32 MB")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_WAV_BYTES:
            raise HTTPException(413, "audio is over 32 MB")
        chunks.append(chunk)
    wav = b"".join(chunks)
    try:
        MuseVoiceAdapter.check_wav(wav)  # refuse a bad file before any budget is reserved
        _guard(Settings()).reserve(VOICE_CALL_ESTIMATE_USD)
        text = await run_in_threadpool(adapter.transcribe, wav)
        if not text:
            raise HTTPException(422, "no speech was recognised")
        return add_note(Settings().runs_dir, run_id, case_id, text, "MUSE_VOICE_TRANSCRIBE")
    except (ValueError, BudgetExceeded) as exc:
        raise HTTPException(422, str(exc)) from exc
    except MetaApiError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/runs/{run_id}/audit")
def audit(run_id: str) -> dict[str, object]:
    """Muse Wonder writes a plain-language audit of a saved run. It never changes a score."""
    cfg = Settings()
    _run_or_404(run_id)
    auditor = _live(lambda: factory.build_wonder_auditor(cfg))
    report = {**load_run(cfg.runs_dir, run_id), **load_extras(cfg.runs_dir, run_id)}
    try:
        _guard(cfg).reserve(WONDER_CALL_ESTIMATE_USD)
        text = auditor.audit(audit_input(report))
    except (BudgetExceeded, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except MetaApiError as exc:
        raise HTTPException(502, str(exc)) from exc
    return save_audit(cfg.runs_dir, run_id, text, auditor.model)


@app.get("/api/scenarios")
def scenario_ids() -> list[str]:
    return list(load_scenarios())


@app.get("/api/scenario")
def scenario(scenario_id: str = "warehouse_001"):
    scenarios = load_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(404, "scenario not found")
    return scenarios[scenario_id]


@app.post("/api/run")
def run(request: RunRequest):
    scenarios = load_scenarios()
    if request.scenario_id not in scenarios:
        raise HTTPException(404, "scenario not found")
    cfg = Settings()
    try:
        agent = build_agent(cfg)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    spends = cfg.provider == "meta" or cfg.planner == "muse"
    if spends and _guard(cfg).exhausted():
        raise HTTPException(429, "this server's spend cap is used up; restart it or raise BLINDSPOT_BUDGET_USD")
    report = agent.run(scenarios[request.scenario_id])
    if report.estimated_cost_usd > 0:
        _guard(cfg).charge(report.calls, report.estimated_cost_usd)
    return report
