from __future__ import annotations

import argparse
import json
import os

import uvicorn

from blindspot_ci.config import Settings
from blindspot_ci.data import load_scenarios
from blindspot_ci.factory import build_agent
from blindspot_ci.media import file_to_data_url


def run_experiment(steps: int, planner: str | None) -> int:
    from blindspot_ci.factory import build_experiment

    try:
        report = build_experiment(planner=planner).run(steps)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        print(exc)
        return 2
    print(f"mode: {report['mode']} | planner: {report['planner']} | dataset: {report['dataset']['type']}")
    for number, step in enumerate(report["steps"], start=1):
        outcome = step["outcome"]
        source = step["prediction"]["source"] if step["prediction"] else "-"
        print(f"{number}. {step['case']['id']:15} {outcome['status']:22} iou={outcome['iou']} [{source}]")
        print(f"   why: {step['decision']['reason']}")
    summary = report["summary"]
    print(f"scored {summary['scored']}: passed {summary['passed']}, failed {summary['failed']}; "
          f"unknown {summary['unknown']}; errors {summary['errors']}; min IoU {summary['min_iou']}")
    for error in report["errors"]:
        print(f"error: {error}")
    print(f"calls {report['calls']}, estimated cost ${report['estimated_cost_usd']}, saved as run {report['id']}")
    return 1 if report["errors"] else 0


def live_run(args) -> int:
    """Run the whole agent loop against the live API on one local image."""
    import dataclasses
    from pathlib import Path

    from blindspot_ci.data import build_custom_scenario

    cfg = Settings()
    if not cfg.model_api_key:
        print("MODEL_API_KEY is not set. Put it in .env on your computer.")
        return 2
    try:
        scenario = build_custom_scenario(file_to_data_url(args.image_file),
                                         [p.strip() for p in args.probes.split(",") if p.strip()], args.truth)
    except ValueError as exc:
        print(exc)
        return 2
    cfg = dataclasses.replace(cfg, provider="meta", planner=args.planner)
    report = build_agent(cfg).run(scenario)
    out = Path("artifacts") / f"live_run_{report.run_id}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    print(f"status: {report.status} | planner: {report.planner} | calls: {report.calls} | "
          f"estimated cost: ${report.estimated_cost_usd:.4f}")
    print(f"  planner note: {report.planner_note}")
    for probe, result in zip(report.probes, report.results, strict=False):
        print(f"  probe {probe:12} detections={len(result.detections)} parser={result.parser_status}")
    for m in report.evaluation.metrics:
        print(f"  {m.label:12} expected={m.tp + m.fn} found={m.tp + m.fp} missed={m.fn} extra={m.fp}")
    for reason in report.review_reasons:
        print(f"  review: {reason}")
    print(f"full report saved to {out}")
    return 0 if report.status in {"complete", "needs_human_review"} else 1


def _raw_call(method: str, url: str, key: str, body: dict | None = None) -> str:
    """One HTTP call, returns 'HTTP status | short body' with the key redacted."""
    import httpx

    try:
        response = httpx.request(method, url, headers={"Authorization": f"Bearer {key}"}, json=body,
                                 timeout=30.0)
        text = response.text[:200].replace("\n", " ").replace(key, "[redacted]")
        return f"HTTP {response.status_code} | {text}"
    except httpx.HTTPError as exc:
        return f"network error: {type(exc).__name__}"


def diagnose() -> int:
    """Separate 'bad key' from 'no model access' from 'wrong model name'. Prints no secrets."""
    cfg = Settings()
    if not cfg.model_api_key:
        print("MODEL_API_KEY is not set.")
        return 2
    key, base = cfg.model_api_key, cfg.meta_base_url.rstrip("/")
    print(f"key length {len(key)}, starts with 'LLM_' (official format): {key.startswith('LLM_')}, "
          f"starts with 'LLM|' (old format): {key.startswith('LLM|')}, underscores {key.count('_')}, "
          f"pipes {key.count('|')}, hyphens {key.count('-')}, letters/digits only: {key.isalnum()}, "
          f"base {base}\n")
    fake = "LLM|0|invalidinvalidinvalid"
    body = {"input": "Return the word READY.", "store": False, "max_output_tokens": 16}
    print("1) Fake key, model muse-spark-1.3:")
    print("  ", _raw_call("POST", f"{base}/responses", fake, {**body, "model": "muse-spark-1.3"}))
    print("2) Your key, GET /models:")
    print("  ", _raw_call("GET", f"{base}/models", key))
    print("3) Your key, other model names:")
    for name in ["muse-spark", "muse-spark-latest", "sam-3.1", "muse-image-1.0", "muse-wonder-1.0"]:
        print(f"   {name:18}", _raw_call("POST", f"{base}/responses", key, {**body, "model": name})[:150])
    print("4) Your key, no model field:")
    print("  ", _raw_call("POST", f"{base}/responses", key, body))
    print("5) Chat Completions route, muse-spark-1.3:")
    print("  ", _raw_call("POST", f"{base}/chat/completions", key,
                          {"model": "muse-spark-1.3", "messages": [{"role": "user", "content": "READY?"}]}))
    return 0




def smoke_text() -> int:
    """One live Muse Spark call. Prints the reply only, never the key."""
    from blindspot_ci.providers.meta import MetaApiError, MetaMuseSparkAdapter

    cfg = Settings()
    if not cfg.model_api_key:
        print("MODEL_API_KEY is not set. Put it in .env on your computer.")
        return 2
    adapter = MetaMuseSparkAdapter(cfg.model_api_key, cfg.meta_base_url)
    adapter.model = cfg.text_model
    try:
        print(f"model {adapter.model}: {adapter.smoke_text()}")
    except MetaApiError as exc:
        print(f"Call failed: {exc}")
        return 1
    return 0


def smoke_tools() -> int:
    """One live Muse Spark function-calling turn. No SAM call, so it costs a fraction of a cent."""
    from blindspot_ci.budget import BudgetGuard
    from blindspot_ci.experiment.cases import load_named_dataset, public_case
    from blindspot_ci.experiment.planners import MuseToolPlanner, PlannerError
    from blindspot_ci.providers.meta import MetaApiError

    cfg = Settings()
    if not cfg.model_api_key:
        print("MODEL_API_KEY is not set. Put it in .env on your computer.")
        return 2
    dataset = load_named_dataset("synthetic")
    public = {cid: public_case(case) for cid, case in dataset.cases.items()}
    planner = MuseToolPlanner(cfg.model_api_key, cfg.meta_base_url, cfg.text_model,
                              BudgetGuard(max_calls=1, max_cost_usd=0.05))
    try:
        decision = planner.choose(public, list(public), [])
    except (PlannerError, MetaApiError, RuntimeError) as exc:
        print(f"Tool-calling check failed: {exc}")
        return 1
    print(f"model {cfg.text_model} chose case {decision.case_id!r} via tool call {decision.tool_call_id!r}")
    print(f"reason: {decision.reason}")
    return 0


def _live_or_exit(build):
    from blindspot_ci.providers.meta import MetaApiError  # noqa: F401

    try:
        return build()
    except PermissionError as exc:
        print(f"{exc} (the helper scripts set LIVE_API_ENABLED for their own session)")
        raise SystemExit(2) from exc


def stress_gen(args) -> int:
    from blindspot_ci import factory
    from blindspot_ci.budget import BudgetExceeded, BudgetGuard
    from blindspot_ci.experiment.cases import load_named_dataset
    from blindspot_ci.experiment.stress import generate_variants, write_manifest
    from blindspot_ci.providers.meta import MetaApiError

    cfg = Settings()
    adapter = _live_or_exit(factory.build_image_adapter)
    try:
        source = load_named_dataset(args.source)
        entries = generate_variants(source, [e.strip() for e in args.edits.split(",") if e.strip()], adapter,
                                    BudgetGuard(cfg.max_calls, cfg.budget_usd),
                                    [c.strip() for c in args.cases.split(",")] if args.cases else None)
    except (ValueError, FileNotFoundError, BudgetExceeded, MetaApiError) as exc:
        print(f"stress-gen failed: {exc}")
        return 1
    path = write_manifest(entries, source)
    print(f"Muse Image made {len(entries)} variants ({', '.join(e['id'] for e in entries)}).")
    print(f"Saved to {path}. They are GENERATED, boxes inherited and not re-verified.")
    print("Run them with BLINDSPOT_DATASET=generated, or pick 'generated' in the web page.")
    return 0


def corrupt_gen(args) -> int:
    from blindspot_ci.experiment.cases import load_named_dataset
    from blindspot_ci.experiment.corruptions import generate_corruptions
    from blindspot_ci.experiment.stress import write_manifest

    try:
        source = load_named_dataset(args.source)
        entries = generate_corruptions(
            source, [c.strip() for c in args.corruptions.split(",") if c.strip()],
            [int(v) for v in args.severities.split(",") if v.strip()],
            [c.strip() for c in args.cases.split(",")] if args.cases else None, args.seed)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"corrupt-gen failed: {exc}")
        return 1
    path = write_manifest(entries, source, name="corrupted")
    print(f"Made {len(entries)} measured corruptions. Labels are exact (no pixel moved). Saved to {path}.")
    print("Run them with: scripts/live_experiment.ps1 -Dataset corrupted -Steps 8")
    return 0


def write_card(args) -> int:
    from pathlib import Path

    from blindspot_ci.experiment.card import build_card
    from blindspot_ci.experiment.reviews import load_extras
    from blindspot_ci.experiment.runner import load_run

    cfg = Settings()
    try:
        run = {**load_run(cfg.runs_dir, args.run), **load_extras(cfg.runs_dir, args.run)}
    except (ValueError, FileNotFoundError) as exc:
        print(f"card failed: {exc}")
        return 1
    out = Path(args.out) if args.out else Path("artifacts") / f"evaluation-card-{args.run}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_card(run), encoding="utf-8")
    print(f"Evaluation card written to {out}")
    return 0


def compare_agent(args) -> int:
    """Score every case once (cached, so repeats are free), then compare the agent's picks with chance."""
    from types import SimpleNamespace

    from blindspot_ci.experiment.baseline import compare_to_random
    from blindspot_ci.experiment.runner import load_run
    from blindspot_ci.factory import build_experiment

    cfg = Settings()
    try:
        run = load_run(cfg.runs_dir, args.run)
        runner = build_experiment(planner="mock")
        order = [s["case"]["id"] for s in run["steps"]]
        failed = {s["case"]["id"]: s["outcome"]["status"].startswith("FAIL") for s in run["steps"]}
        for case_id in runner.dataset.cases:
            if case_id not in failed:
                step = runner._test_case("baseline", runner.dataset.cases[case_id],
                                         SimpleNamespace(case_id=case_id, reason="baseline", planner="BASELINE",
                                                         tool_call_id=None))
                failed[case_id] = step["outcome"]["status"].startswith("FAIL")
        result = compare_to_random([failed[c] for c in order], len(runner.dataset.cases), sum(failed.values()))
    except (ValueError, FileNotFoundError, PermissionError, RuntimeError) as exc:
        print(f"compare-agent failed: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


def replay_planner(args) -> int:
    """Replay an offline planner against statuses from a saved run."""
    from blindspot_ci.experiment.planners import MockToolPlanner
    from blindspot_ci.experiment.replay import ReplayError
    from blindspot_ci.experiment.replay import replay_planner as run_replay
    from blindspot_ci.experiment.runner import load_run

    if args.planner != "mock":
        print("replay-planner failed: MuseToolPlanner is refused because replay makes zero network calls")
        return 1
    try:
        run = load_run(Settings().runs_dir, args.run)
        result = run_replay(run, MockToolPlanner(), args.steps)
    except (ReplayError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"replay-planner failed: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


def transcribe_note(args) -> int:
    from pathlib import Path

    from blindspot_ci import factory
    from blindspot_ci.experiment.reviews import add_note
    from blindspot_ci.providers.meta import MetaApiError

    adapter = _live_or_exit(factory.build_voice_adapter)
    try:
        text = adapter.transcribe(Path(args.wav).read_bytes())
        print(f"transcript: {text!r}")
        if args.run and args.case:
            add_note(Settings().runs_dir, args.run, args.case, text, "MUSE_VOICE_TRANSCRIBE")
            print(f"saved as a reviewer note on run {args.run}, case {args.case}")
    except (ValueError, OSError, FileNotFoundError, MetaApiError) as exc:
        print(f"transcribe failed: {exc}")
        return 1
    return 0


def audit_run(args) -> int:
    from blindspot_ci import factory
    from blindspot_ci.experiment.reviews import load_extras, save_audit
    from blindspot_ci.experiment.runner import load_run
    from blindspot_ci.providers.meta import MetaApiError
    from blindspot_ci.providers.meta_extras import audit_input

    auditor = _live_or_exit(factory.build_wonder_auditor)
    cfg = Settings()
    try:
        report = {**load_run(cfg.runs_dir, args.run), **load_extras(cfg.runs_dir, args.run)}
        text = auditor.audit(audit_input(report))
    except (ValueError, FileNotFoundError, MetaApiError) as exc:
        print(f"audit failed: {exc}")
        return 1
    save_audit(cfg.runs_dir, args.run, text, auditor.model)
    print(text)
    return 0


def smoke_models(wav: str | None) -> int:
    """One tiny live call each to Muse Wonder, Muse Image and Muse Voice Transcribe."""
    from pathlib import Path

    from blindspot_ci import factory
    from blindspot_ci.providers.meta import MetaApiError

    status = 0
    sample = Path(__file__).resolve().parents[1] / "datasets" / "samples" / "normal.png"
    try:
        text = _live_or_exit(factory.build_wonder_auditor).audit(
            {"mode": "MOCK_FIXTURE", "dataset": {"type": "smoke test"}, "steps": [], "summary": {}})
        print(f"muse-wonder-1.0: replied, {len(text)} characters")
    except (MetaApiError, ValueError) as exc:
        print(f"muse-wonder-1.0 FAILED: {exc}")
        status = 1
    try:
        raw = _live_or_exit(factory.build_image_adapter).edit(
            sample.read_bytes(), "image/png", "Make this image slightly darker. Keep all shapes in place.")
        print(f"muse-image-1.0: returned {len(raw):,} image bytes")
    except (MetaApiError, ValueError, OSError) as exc:
        print(f"muse-image-1.0 FAILED: {exc}")
        status = 1
    if wav:
        try:
            print(f"muse-voice-transcribe-1.0: {_live_or_exit(factory.build_voice_adapter).transcribe(Path(wav).read_bytes())!r}")
        except (MetaApiError, ValueError, OSError) as exc:
            print(f"muse-voice-transcribe-1.0 FAILED: {exc}")
            status = 1
    else:
        print("muse-voice-transcribe-1.0: skipped (pass --wav FILE)")
    return status


def smoke_sam(image_url: str | None, image_file: str | None, prompt: str) -> int:
    """One live call. Prints a summary only: never the key and never the full raw payload."""
    from blindspot_ci.models import Scenario
    from blindspot_ci.providers.meta import MetaApiError, MetaSam31Adapter

    cfg = Settings()
    if not cfg.model_api_key:
        print("MODEL_API_KEY is not set. Put it in .env on your computer.")
        return 2
    try:
        image_url = file_to_data_url(image_file) if image_file else image_url
    except ValueError as exc:
        print(exc)
        return 2
    if not image_url:
        print("Give --image-file PATH or --image-url URL")
        return 2
    scenario = Scenario(id="smoke", description="smoke test", image_url=image_url,
                        probe_catalog=[prompt], ground_truth=[])
    try:
        adapter = MetaSam31Adapter(cfg.model_api_key, cfg.meta_base_url)
        adapter.model, adapter.stream = cfg.sam_model, cfg.sam_stream
        result = adapter.inspect(scenario, prompt)
    except (MetaApiError, ValueError) as exc:
        print(f"Call failed: {exc}")
        if "robots" in str(exc):
            print("Hint: that host blocks Meta's image fetcher. Use --image-file with a local copy instead.")
        return 1
    print(json.dumps({"model": result.model, "parser_status": result.parser_status,
                      "parser_notes": result.parser_notes, "detections": len(result.detections),
                      "boxes": [d.metadata.get("box_xyxy") for d in result.detections],
                      "usage": result.usage, "raw_text_preview": (result.raw_text or "")[:120]},
                     indent=2))
    return 0 if result.parser_status == "structured" else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="blindspot")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    run = sub.add_parser("run-fixture")
    run.add_argument("--scenario", default="warehouse_001")
    run.add_argument("--image-url", help="public https image to use instead of the fixture value")
    run.add_argument("--image-file", help="local jpg/png/webp, sent to the API as a data URL")
    sub.add_parser("serve")
    imp = sub.add_parser("import-photos", help="import human-labeled photos into the private real dataset")
    imp.add_argument("labels_json")
    imp.add_argument("--force", action="store_true")
    imp.add_argument("--dataset", choices=["real", "open", "hard", "video", "coco"], default="real")
    exp = sub.add_parser("experiment", help="case-based experiment: planner picks tests, SAM observes, Python scores")
    exp.add_argument("--steps", type=int, default=5)
    exp.add_argument("--planner", choices=["mock", "muse"], default=None)
    live = sub.add_parser("live-run", help="full agent run on your own image with human-verified truth")
    live.add_argument("--image-file", required=True)
    live.add_argument("--probes", required=True, help="comma list, e.g. person,bus,stop_sign")
    live.add_argument("--truth", required=True, help="what is really in the image, e.g. person=4,bus=1:high")
    live.add_argument("--planner", choices=["heuristic", "muse"], default="heuristic")
    sub.add_parser("smoke-meta")
    sub.add_parser("smoke-tools", help="one live Muse Spark function-calling turn (no SAM call)")
    lab = sub.add_parser("label", help="local tool: you draw the box on each photo in a folder")
    lab.add_argument("--folder", required=True, help="folder of upright-viewable jpg or png photos")
    lab.add_argument("--annotator", required=True, help="your name; stored with every label")
    lab.add_argument("--out", default="my-labels.json")
    lab.add_argument("--concept", default="red safety tag")
    lab.add_argument("--port", type=int, default=8001)
    adj = sub.add_parser("adjudicate", help="a named person marks a doubtful label unknown (not scored, original kept)")
    adj.add_argument("--dataset", choices=["real", "open", "hard", "video", "coco"], default="open")
    adj.add_argument("--case", required=True)
    adj.add_argument("--by", required=True, help="the person making the call")
    adj.add_argument("--reason", required=True)
    sg = sub.add_parser("stress-gen", help="Muse Image makes labeled GENERATED variants (about $0.01 each)")
    sg.add_argument("--source", choices=["synthetic", "real", "open", "hard", "video", "coco"], default="real")
    sg.add_argument("--edits", default="low_light,glare", help="comma list: low_light, glare, motion_blur")
    sg.add_argument("--cases", default="", help="comma list of source case ids (default: all visible)")
    cg = sub.add_parser("corrupt-gen", help="measured corruptions of labeled photos (free, labels stay exact)")
    cg.add_argument("--source", choices=["synthetic", "real", "open", "hard", "video", "coco"], default="real")
    cg.add_argument("--corruptions", default="low_light,noise,blur", help="low_light, noise, blur, jpeg, fog, contrast")
    cg.add_argument("--severities", default="3", help="comma list from 1 to 5")
    cg.add_argument("--cases", default="")
    cg.add_argument("--seed", type=int, default=7)
    cd = sub.add_parser("card", help="write the Markdown evaluation card for a saved run")
    cd.add_argument("--run", required=True)
    cd.add_argument("--out")
    cr = sub.add_parser("compare-runs", help="regression gate: candidate run versus baseline run on the same cases")
    cr.add_argument("--baseline", required=True)
    cr.add_argument("--candidate", required=True)
    cv = sub.add_parser("coverage", help="case counts per dataset and condition, no model calls")
    cv.add_argument("--dataset")
    cv.add_argument("--format", choices=["text", "markdown"], default="text")
    cl = sub.add_parser("compare-labels", help="agreement between two people who labeled the same photos")
    cl.add_argument("first")
    cl.add_argument("second")
    ca = sub.add_parser("compare-agent", help="agent's tests versus random order, exact (scores every case once)")
    ca.add_argument("--run", required=True)
    rp = sub.add_parser("replay-planner", help="compare an offline test-ordering policy on saved outcomes")
    rp.add_argument("--run", required=True)
    rp.add_argument("--steps", type=int, required=True)
    rp.add_argument("--planner", choices=["mock", "muse"], default="mock")
    tr = sub.add_parser("transcribe", help="Muse Voice Transcribe: WAV to text, optionally saved as a reviewer note")
    tr.add_argument("--wav", required=True)
    tr.add_argument("--run")
    tr.add_argument("--case")
    au = sub.add_parser("audit", help="Muse Wonder writes a plain-language audit of a saved run")
    au.add_argument("--run", required=True)
    sm = sub.add_parser("smoke-models", help="one tiny live call each to Muse Wonder, Image and Voice")
    sm.add_argument("--wav", help="16 kHz mono WAV for the Muse Voice Transcribe check")
    sub.add_parser("diagnose", help="compare your key with a fake key and test more model names")
    smoke = sub.add_parser("smoke-sam", help="one authorized SAM 3.1 call on a public https image")
    smoke.add_argument("--image-url", help="public https image (host must allow Meta's fetcher in robots.txt)")
    smoke.add_argument("--image-file", help="local jpg/png/webp, sent as a data URL (avoids robots.txt problems)")
    smoke.add_argument("--prompt", default="person")
    args = parser.parse_args()
    if args.command == "serve":
        host = os.environ.get("BLINDSPOT_HOST", "127.0.0.1")
        port = int(os.environ.get("BLINDSPOT_PORT", "8000"))
        if host not in {"127.0.0.1", "localhost", "::1"} and Settings().live_api_enabled:
            raise SystemExit("refusing to serve a live key on a public address: set LIVE_API_ENABLED=false "
                             "or bind BLINDSPOT_HOST=127.0.0.1")
        uvicorn.run("blindspot_ci.api:app", host=host, port=port, reload=False)
        return
    if args.command == "import-photos":
        from pathlib import Path

        from blindspot_ci.experiment.importer import import_labeled

        try:
            count = import_labeled(Path(args.labels_json), force=args.force, name=args.dataset)
        except (ValueError, FileExistsError, FileNotFoundError, KeyError) as exc:
            raise SystemExit(f"import failed: {exc!r}") from exc
        print(f"Imported {count} human-labeled photos. Set BLINDSPOT_DATASET={args.dataset} to use them.")
        return
    if args.command == "experiment":
        raise SystemExit(run_experiment(args.steps, args.planner))
    if args.command == "live-run":
        raise SystemExit(live_run(args))
    if args.command == "label":
        from pathlib import Path

        from blindspot_ci.labeler import create_app

        try:
            labeler = create_app(Path(args.folder), Path(args.out), args.annotator, args.concept)
        except (ValueError, OSError) as exc:
            raise SystemExit(f"label failed: {exc}") from exc
        print(f"Open http://127.0.0.1:{args.port} and draw a box on each photo. Labels save to {args.out}.")
        print(f"Then: python -m blindspot_ci.cli import-photos {args.out}")
        uvicorn.run(labeler, host="127.0.0.1", port=args.port)
        return
    if args.command == "adjudicate":
        from blindspot_ci.experiment.importer import adjudicate

        try:
            adjudicate(args.case, args.reason, args.by, args.dataset)
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(f"adjudicate failed: {exc}") from exc
        print(f"{args.case} is now unknown (not scored). The original label is kept in label_provenance.")
        return
    if args.command == "corrupt-gen":
        raise SystemExit(corrupt_gen(args))
    if args.command == "coverage":
        from blindspot_ci.experiment.coverage import load_matrix, render

        print(render(load_matrix(args.dataset), args.format))
        return
    if args.command == "card":
        raise SystemExit(write_card(args))
    if args.command == "compare-runs":
        import json as _json

        from blindspot_ci.experiment.regression import compare_runs
        from blindspot_ci.experiment.runner import load_run

        try:
            runs_dir = Settings().runs_dir
            report = compare_runs(load_run(runs_dir, args.baseline), load_run(runs_dir, args.candidate))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"compare-runs failed: {exc}") from exc
        print(_json.dumps(report, indent=2))
        raise SystemExit(1 if report["verdict"].startswith("FAIL") else 0)
    if args.command == "compare-labels":
        import json as _json
        from pathlib import Path as _Path

        from blindspot_ci.experiment.agreement import compare_labels

        try:
            report = compare_labels(*[_json.loads(_Path(p).read_text(encoding="utf-8")) for p in (args.first, args.second)])
        except (OSError, ValueError, KeyError) as exc:
            raise SystemExit(f"compare-labels failed: {exc}") from exc
        print(_json.dumps(report, indent=2))
        return
    if args.command == "compare-agent":
        raise SystemExit(compare_agent(args))
    if args.command == "replay-planner":
        raise SystemExit(replay_planner(args))
    if args.command == "stress-gen":
        raise SystemExit(stress_gen(args))
    if args.command == "transcribe":
        raise SystemExit(transcribe_note(args))
    if args.command == "audit":
        raise SystemExit(audit_run(args))
    if args.command == "smoke-models":
        raise SystemExit(smoke_models(args.wav))
    if args.command == "diagnose":
        raise SystemExit(diagnose())
    if args.command == "smoke-meta":
        raise SystemExit(smoke_text())
    if args.command == "smoke-tools":
        raise SystemExit(smoke_tools())
    if args.command == "smoke-sam":
        raise SystemExit(smoke_sam(args.image_url, args.image_file, args.prompt))
    scenario_id = "warehouse_001" if args.command == "demo" else args.scenario
    scenarios = load_scenarios()
    if scenario_id not in scenarios:
        raise SystemExit(f"unknown scenario '{scenario_id}'. Choose from: {', '.join(scenarios)}")
    scenario = scenarios[scenario_id]
    image = getattr(args, "image_url", None)
    if getattr(args, "image_file", None):
        try:
            image = file_to_data_url(args.image_file)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    if image:
        scenario = scenario.model_copy(update={"image_url": image})
    report = build_agent().run(scenario)
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    main()
