import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from blindspot_ci import cli
from blindspot_ci.experiment import temporal
from blindspot_ci.experiment.release_gate import evaluate, load_policy
from blindspot_ci.experiment.runner import load_run
from blindspot_ci.experiment.temporal import (
    build_sequence_request,
    plan_long_video,
    render_temporal_report,
    run_long_video,
)
from blindspot_ci.providers.sam_video import MetaSam31VideoAdapter, VideoResult

KEY = "LLM_test_key"


class _CutStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"type":"response.output_text.delta","delta":"<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\\n"}\n\n'
        raise RuntimeError("connection cut")


class _StallStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"type":"response.output_text.delta","delta":"<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\\n"}\n\n'
        yield b"\n"


class _TotalTimeoutStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"type":"response.output_text.delta","delta":"<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\\n"}\n\n'
        yield b'data: {"type":"response.output_text.delta","delta":"<2f>1<|box;x1=0;y1=0;x2=10;y2=10|>\\n"}\n\n'


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


def test_edge_seed_is_clamped_but_original_human_box_scores(tmp_path):
    manifest = _manifest()
    target = manifest["sequences"][0]["targets"][0]
    target["seed_box"] = [0, 0, 10, 100]
    target["frames"][0]["box"] = [0, 0, 10, 100]
    request, clamped = build_sequence_request(manifest["sequences"][0])
    prompt_text = request.body["input"][0]["content"][0]["text"]
    assert clamped == 1 and ";y2=99;" in prompt_text
    body = _sse(_delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=100|>\n"), _complete())
    report = run_long_video(manifest, ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=_adapter(body))
    saved = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    sequence = saved["sequences"][0]
    assert sequence["seed_boxes_clamped"] == 1
    assert sequence["targets"][0]["frames"][0]["human_box"] == [0, 0, 10, 100]
    assert sequence["targets"][0]["frames"][0]["status"] == "PASS"
    assert "Seed boxes clamped inside the frame: 1" in render_temporal_report(tmp_path / "runs", report["id"])


def test_model_boxes_scale_from_reported_frame_size(tmp_path):
    manifest = _manifest()
    sequence = manifest["sequences"][0]
    sequence["frame_size"] = [1173, 880]
    sequence["targets"][0]["seed_box"] = [1127, 832, 1171, 878]
    sequence["targets"][0]["frames"][0]["box"] = [1127, 832, 1171, 878]
    body = _sse(_delta("<1f>1<|box;x1=563;y1=416;x2=585;y2=439;w=586;h=440|>\n"), _complete())
    report = run_long_video(manifest, ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=_adapter(body))
    data = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    sequence_result = data["sequences"][0]
    row = sequence_result["targets"][0]["frames"][0]
    assert row["status"] == "PASS"
    assert row["model_box"] == [1127, 832, 1171, 878]
    assert sequence_result["output_frame_size"] == [[586, 440]]
    assert sequence_result["scale_x"] == pytest.approx(1173 / 586, abs=1e-6)
    assert sequence_result["scale_y"] == pytest.approx(2.0)
    assert "The service returned boxes at 586 by 440" in render_temporal_report(tmp_path / "runs", report["id"])


def test_model_box_without_frame_size_uses_request_pixels(tmp_path):
    body = _sse(_delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"), _complete())
    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=_adapter(body))
    data = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    sequence_result = data["sequences"][0]
    assert sequence_result["targets"][0]["frames"][0]["model_box"] == [0, 0, 10, 10]
    assert sequence_result["output_frame_size"] == []


def test_distinct_reported_frame_sizes_are_recorded(tmp_path):
    manifest = _manifest()
    sequence = manifest["sequences"][0]
    sequence["frame_size"] = [1173, 880]
    sequence["targets"][0]["seed_box"] = [1127, 832, 1171, 878]
    sequence["targets"][0]["frames"][0]["box"] = [1127, 832, 1171, 878]
    body = _sse(
        _delta("<1f>1<|box;x1=563;y1=416;x2=585;y2=439;w=586;h=440|>\n"),
        _delta("<2f>1<|box;x1=1127;y1=832;x2=1171;y2=878;w=1173;h=880|>\n"),
        _complete())
    report = run_long_video(manifest, ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=_adapter(body))
    data = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    sequence_result = data["sequences"][0]
    assert sequence_result["output_frame_size"] == [[586, 440], [1173, 880]]
    assert sequence_result["scale_x"] == pytest.approx([1173 / 586, 1.0], abs=1e-6)
    assert sequence_result["scale_y"] == pytest.approx([2.0, 1.0], abs=1e-6)


def test_stall_guard_marks_partial_stream_truncated(monkeypatch, tmp_path):
    clock = iter([0.0, 0.0, 181.0])
    monkeypatch.setattr(temporal, "_monotonic", lambda: next(clock))

    def handler(request):
        return httpx.Response(200, stream=_StallStream())

    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw",
                            adapter=MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler)))
    data = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    rows = data["sequences"][0]["targets"][0]["frames"]
    assert rows[0]["status"] == "PASS"
    assert rows[1]["status"] == "ERROR"
    assert (tmp_path / "raw" / f"{report['id']}-MOT20-02.txt").read_text().startswith("data:")


def test_total_stream_guard_marks_partial_stream_truncated(monkeypatch, tmp_path):
    clock = iter([0.0, 0.0, 1501.0])
    monkeypatch.setattr(temporal, "_monotonic", lambda: next(clock))
    monkeypatch.setattr(temporal, "STREAM_IDLE_TIMEOUT_SECONDS", 10_000.0)

    def handler(request):
        return httpx.Response(200, stream=_TotalTimeoutStream())

    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw",
                            adapter=MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler)))
    data = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    rows = data["sequences"][0]["targets"][0]["frames"]
    assert rows[0]["status"] == "PASS"
    assert rows[1]["status"] == "ERROR"


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
    assert "miss runs; recovery median" in text
    assert "target not returned" in text
    assert "box returned but below the overlap bar" in text
    assert "Target retention" in text
    assert "hidden parts" in text and "fixed-camera" in text
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
    assert report["calls"] == 1 and report["estimated_cost_usd"] == 0.0
    assert "request refused before processing, reservation released" in report["errors"][0]
    temporal = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    assert temporal["estimated_cost_usd"] == 0.0


def test_cut_stream_keeps_partial_raw_and_marks_later_frames_error(tmp_path):
    def handler(request):
        return httpx.Response(200, stream=_CutStream())

    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw",
                            adapter=MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler)))
    temporal = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    rows = temporal["sequences"][0]["targets"][0]["frames"]
    assert rows[0]["status"] == "PASS"
    assert rows[1]["status"] == "ERROR" and "ended early" in rows[1]["reason"]
    assert (tmp_path / "raw" / f"{report['id']}-MOT20-02.txt").read_text().startswith("data:")


def test_raw_safety_cap_stops_reading_and_marks_truncated(monkeypatch, tmp_path):
    monkeypatch.setattr(temporal, "MAX_RAW_TEXT_BYTES", 10)
    body = _sse(_delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"), _complete())
    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=_adapter(body))
    raw_path = tmp_path / "raw" / f"{report['id']}-MOT20-02.txt"
    assert raw_path.stat().st_size <= 10
    saved = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    assert saved["sequences"][0]["targets"][0]["frames"][0]["status"] == "ERROR"


def test_missing_middle_frame_in_completed_stream_is_a_miss(tmp_path):
    body = _sse(
        _delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"),
        _delta("<3f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"),
        _complete(),
    )
    report = run_long_video(_manifest(), ["MOT20-02"], 1.0,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=_adapter(body))
    temporal = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    rows = temporal["sequences"][0]["targets"][0]["frames"]
    assert rows[1]["status"] == "FAIL_FALSE_NEGATIVE"
    assert rows[2]["status"] == "PASS"


def test_raw_replay_needs_no_live_settings_and_costs_zero(monkeypatch, tmp_path, capsys):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    body = _sse(_delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"), _complete())
    (raw_dir / "saved-MOT20-02.txt").write_text(body, encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    monkeypatch.setattr(cli, "Settings", lambda: SimpleNamespace(runs_dir=tmp_path / "runs"))
    args = SimpleNamespace(manifest=str(manifest_path), sequences=["MOT20-02"], budget_usd=None,
                           dry_run=False, min_iou=0.35, from_raw=str(raw_dir))
    assert cli.long_video(args) == 0
    report_path = next((tmp_path / "runs").glob("[0-9a-f]*.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["mode"] == "CACHE_LIVE_META"
    assert report["estimated_cost_usd"] == 0.0
    assert report["replayed_from_raw"].endswith("saved-MOT20-02.txt")
    assert "replayed raw text" in capsys.readouterr().out


def test_video_file_dry_run_reports_bytes_without_live_settings(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"offline clip")
    args = SimpleNamespace(manifest=str(manifest_path), sequences=["MOT20-02"], budget_usd=1.0,
                           dry_run=True, min_iou=0.35, from_raw=None,
                           video_file=str(video_path), allow_upload=False)
    assert cli.long_video(args) == 0
    output = capsys.readouterr().out
    assert "would upload 12 bytes" in output
    assert "no network call made" in output


def test_video_file_upload_lifecycle_uses_file_id_and_records_deletion(monkeypatch, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"offline clip")
    seen = []

    class FakeAdapter:
        api_key = "test-key"

        def __init__(self, *args, **kwargs):
            pass

        def upload_file(self, path):
            seen.append(("upload", Path(path).name))
            return "file-123"

        def delete_file(self, file_id):
            seen.append(("delete", file_id))
            return {"id": file_id, "deleted": True}

        def track(self, request, frames, budget):
            seen.append(("track", request.body["input"][0]["content"][1]))
            budget.reserve(frames * 0.0002)
            parsed = temporal.parse_video_stream(
                _sse(_delta("<1f>1<|box;x1=0;y1=0;x2=10;y2=10|>\n"), _complete()).splitlines())
            return VideoResult(parsed, request.id_to_label, frames * 0.0002, None)

    monkeypatch.setattr("blindspot_ci.providers.sam_video.MetaSam31VideoAdapter", FakeAdapter)
    monkeypatch.setattr(cli, "Settings", lambda: SimpleNamespace(
        provider="meta", live_api_enabled=True, model_api_key="test-key",
        meta_base_url="https://example.invalid/v1", runs_dir=tmp_path / "runs"))
    args = SimpleNamespace(manifest=str(manifest_path), sequences=["MOT20-02"], budget_usd=1.0,
                           dry_run=False, min_iou=0.35, from_raw=None,
                           video_file=str(video_path), allow_upload=True)
    assert cli.long_video(args) == 0
    assert seen == [("upload", "clip.mp4"), ("track", {"type": "input_video", "file_id": "file-123"}),
                    ("delete", "file-123")]
    report_path = next(path for path in (tmp_path / "runs").glob("[0-9a-f]*.json")
                       if not path.name.endswith(".temporal.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["video_file_uploaded"] is True and report["video_file_deleted"] is True


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
                           dry_run=False, min_iou=0.35, from_raw=None)
    assert cli.long_video(args) == 2
    assert expected in capsys.readouterr().out
