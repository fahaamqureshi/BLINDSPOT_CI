import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from blindspot_ci import cli
from blindspot_ci.experiment.release_gate import evaluate, load_policy
from blindspot_ci.experiment.runner import load_run
from blindspot_ci.experiment.temporal import (
    plan_long_video,
    render_temporal_report,
    run_long_video,
)
from blindspot_ci.providers.sam_video import MetaSam31VideoAdapter

KEY = "LLM_test_key"


def _sse(*events):
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


def _delta(text):
    return {"type": "response.output_text.delta", "delta": text}


def _complete(frames=60):
    return {"type": "response.completed", "response": {"usage": {"video_frames_processed": frames}}}


def _manifest(frame_count=60):
    rows = []
    for frame in range(1, frame_count + 1):
        rows.append({"frame": frame, "status": "SCORED", "box": [0, 0, 10, 10],
                     "visibility": 1, "tags": ["occluded" if frame == 2 else "normal"]})
    rows[4] = {"frame": 5, "status": "NOT_SCORED", "box": None, "visibility": None,
               "tags": ["NOT_SCORED"]}
    return {"dataset": "MOT20", "sequences": [{
        "name": "MOT20-02", "source_url": "https://example.invalid/clip.mp4", "fps": 25,
        "frame_size": [100, 100], "frame_count": frame_count,
        "luminance_samples": [{"frame": 1, "mean_luminance": 20},
                               {"frame": frame_count, "mean_luminance": 80}],
        "targets": [{"track_id": 7, "seed_frame": 1, "seed_box": [0, 0, 10, 10],
                     "frames": rows}],
    }]}


def _adapter(body, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, text=body)

    return MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler))


def test_plan_and_dry_cost_are_offline():
    plan = plan_long_video(_manifest(), ["MOT20-02"], 1.0)
    assert plan[0]["frames"] == 60
    assert plan[0]["cost_usd"] == pytest.approx(60 * 0.0002)


def test_long_video_scores_raw_output_and_temporal_metrics(tmp_path):
    body = _sse(
        _delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"),
        _delta("<1f>1<|box;x1=20;y1=20;x2=30;y2=30|>\n"),
        _delta("<2f>\n<3f>1<|box;x1=20;y1=20;x2=30;y2=30|>\n"),
        _delta("<6f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"),
        _complete(),
    )
    raw = tmp_path / "raw"
    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=raw, adapter=_adapter(body))
    run = load_run(tmp_path / "runs", report["id"])
    temporal = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    rows = temporal["sequences"][0]["targets"][0]["frames"]
    assert rows[0]["status"] == "PASS"
    assert temporal["sequences"][0]["targets"][0]["duplicate_count"] == 1
    assert rows[1]["status"] == "FAIL_FALSE_NEGATIVE"
    assert rows[2]["status"] == "FAIL_LOCALIZATION"
    assert rows[4]["status"] == "NOT_SCORED"
    assert rows[5]["status"] == "PASS"
    assert (raw / f"{report['id']}-MOT20-02.txt").read_text().startswith("data:")
    assert run["mode"] == "LIVE_META" and run["planner"] == "SEEDED_BOX_TRACKING"
    assert load_policy(Path("fixtures/policies/long-video.json"))["required_conditions"] == [
        "occluded", "truncated", "dark", "small_object"]
    gate = evaluate(run, load_policy(Path("fixtures/policies/long-video.json")))
    assert gate["decision"] in {"NEEDS_REVIEW", "NO_GO"}
    text = render_temporal_report(tmp_path / "runs", report["id"])
    assert "ten equal time bins" in text
    assert "never recovered" in text
    assert "strongly correlated" in text


def test_budget_stops_before_transport(tmp_path):
    seen = []
    body = _sse(_complete())
    report = run_long_video(_manifest(), ["MOT20-02"], 0.001,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw",
                            adapter=_adapter(body, seen))
    assert seen == []
    assert report["calls"] == 0 and report["errors"]


def test_http_500_is_one_attempt_and_raw_is_saved(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, text="server failed")

    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw",
                            adapter=MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler)))
    assert len(calls) == 1
    assert (tmp_path / "raw" / f"{report['id']}-MOT20-02.txt").read_text() == "server failed"


@pytest.mark.parametrize("provider,enabled,key,expected", [
    ("mock", True, "LLM_test_key", "BLINDSPOT_PROVIDER"),
    ("meta", False, "LLM_test_key", "LIVE_API_ENABLED"),
    ("meta", True, None, "MODEL_API_KEY"),
])
def test_live_requirements_fail_before_network(monkeypatch, capsys, tmp_path, provider, enabled, key, expected):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    monkeypatch.setattr(cli, "Settings", lambda: SimpleNamespace(
        provider=provider, live_api_enabled=enabled, model_api_key=key,
        meta_base_url="https://example.invalid/v1", runs_dir=tmp_path / "runs"))
    args = SimpleNamespace(manifest=str(manifest_path), sequences=["MOT20-02"], budget_usd=1.0,
                           dry_run=False, min_iou=0.35)
    assert cli.long_video(args) == 2
    assert expected in capsys.readouterr().out
