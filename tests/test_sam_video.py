import json

import httpx
import pytest

from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.providers.meta import MetaApiError
from blindspot_ci.providers.sam_video import (
    VIDEO_UPLOAD_MAX_BYTES,
    VIDEO_USD_PER_FRAME,
    MetaSam31VideoAdapter,
    VideoBoxPrompt,
    build_video_request,
    estimate_cost,
    parse_video_stream,
    parse_video_text,
    reserve_cost,
)

MASK = "<|mask;x=0;y=0;c=0.9;data=27,60,!abc|>"
F0 = ("<0f>1<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334;c=0.96|>" + MASK
      + ",2<|box;x1=155;y1=228;x2=202;y2=254;w=320;h=334;c=0.5|>" + MASK)
F1 = "<1f>1<|box;x1=212;y1=229;x2=271;y2=255;w=320;h=334;c=0.9|>" + MASK
KEY = "sk-test-secret"


def sse(*events):
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events)


def delta(text):
    return {"type": "response.output_text.delta", "delta": text}


def completed(frames=60):
    return {"type": "response.completed", "response": {"usage": {"video_frames_processed": frames}}}


def prompts():
    return [VideoBoxPrompt("cat", (10, 20, 50, 60), 0), VideoBoxPrompt("dog", (70, 20, 90, 60), 0),
            VideoBoxPrompt("cat", (12, 22, 52, 62), 30)]


def test_two_frames_two_objects():
    result = parse_video_text(F0 + "\n" + F1 + "\n")
    assert [f.frame_index for f in result.frames] == [0, 1]
    assert result.frames[0].objects == [
        {"object_id": 1, "box_xyxy_pixels": [211, 228, 270, 254], "confidence": 0.96},
        {"object_id": 2, "box_xyxy_pixels": [155, 228, 202, 254], "confidence": 0.5}]
    assert len(result.frames[1].objects) == 1 and result.malformed == 0


def test_frames_concatenated_without_newline_are_split():
    result = parse_video_text(F0 + F1)
    assert [f.frame_index for f in result.frames] == [0, 1]


def test_cut_off_stream_is_truncated_and_keeps_parsed_frames():
    text = sse(delta(F0), delta(F1[:40]))
    result = parse_video_stream(text.splitlines())
    assert result.truncated and not result.completed
    assert [f.frame_index for f in result.frames] == [0]
    assert result.malformed == 1


def test_complete_stream_reports_usage():
    result = parse_video_stream(sse(delta(F0), delta(F1), completed(60)).splitlines())
    assert result.completed and not result.truncated
    assert result.usage["video_frames_processed"] == 60


def test_duplicate_frame_marker_is_not_merged():
    result = parse_video_text(F0 + "\n" + F1 + "\n" + F1.replace("212", "200") + "\n")
    assert [f.frame_index for f in result.frames] == [0, 1, 1]
    assert result.duplicate_frames == [1]
    assert result.frames[1].objects != result.frames[2].objects


def test_out_of_order_frames_keep_arrival_order():
    result = parse_video_text(F1 + "\n" + F0 + "\n")
    assert [f.frame_index for f in result.frames] == [1, 0] and result.out_of_order


def test_empty_frame_has_no_objects():
    result = parse_video_text("<5f>\n" + F0)
    assert result.frames[0].frame_index == 5 and result.frames[0].objects == []
    assert result.malformed == 0


def test_malformed_lines_are_skipped_and_counted():
    bad = "garbage\n<3f>1<|box;x1=a;y1=1|>\n" + F0 + "\n<4f>1<|box;x1=9;y1=1;x2=2;y2=2|>\n"
    result = parse_video_text(bad)
    assert [f.frame_index for f in result.frames] == [0]
    assert result.malformed == 3


def test_missing_confidence_is_none():
    result = parse_video_text("<0f>1<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>" + MASK)
    assert result.frames[0].objects[0]["confidence"] is None


def test_cost_and_minimum():
    assert VIDEO_USD_PER_FRAME == pytest.approx(0.0002)
    assert estimate_cost(10) == pytest.approx(50 * 0.0002)
    assert estimate_cost(1000) == pytest.approx(0.20)
    with pytest.raises(ValueError):
        estimate_cost(15001)
    with pytest.raises(ValueError):
        estimate_cost(0)


def test_reserve_cost_uses_guard():
    guard = BudgetGuard(max_calls=1, max_cost_usd=0.05)
    assert reserve_cost(guard, 100) == pytest.approx(0.02)
    assert guard.calls == 1 and guard.cost_usd == pytest.approx(0.02)
    with pytest.raises(BudgetExceeded):
        reserve_cost(guard, 100)
    with pytest.raises(BudgetExceeded):
        reserve_cost(BudgetGuard(max_calls=5, max_cost_usd=0.001), 100)


def test_request_body_shape():
    req = build_video_request(prompts(), frame_width=100, frame_height=100, file_id="file-1",
                              propagation_direction="forward")
    body = req.body
    assert body["model"] == "sam-3.1" and body["stream"] is True
    assert body["metadata"] == {"propagation_direction": "forward", "include_confidence": "true",
                                "mask_encoding": "one_bit"}
    text, video = body["input"][0]["content"]
    assert video == {"type": "input_video", "file_id": "file-1"}
    assert text["text"] == (
        "<0f>1<|box;x1=10;y1=20;x2=50;y2=60;w=100;h=100|>,2<|box;x1=70;y1=20;x2=90;y2=60;w=100;h=100|>"
        "<30f>1<|box;x1=12;y1=22;x2=52;y2=62;w=100;h=100|>")
    assert req.id_to_label == {1: "cat", 2: "dog"}
    url = build_video_request(prompts(), frame_width=100, frame_height=100, video_url="https://x/y.mp4")
    assert url.body["input"][0]["content"][1] == {"type": "input_video", "video_url": "https://x/y.mp4"}


def test_request_validation():
    kw = {"frame_width": 100, "frame_height": 100, "video_url": "https://x/y.mp4"}
    with pytest.raises(ValueError):
        build_video_request(prompts(), frame_width=100, frame_height=100)  # no source
    with pytest.raises(ValueError):
        build_video_request(prompts(), frame_width=100, frame_height=100, video_url="u", file_id="f")
    with pytest.raises(ValueError):
        build_video_request(prompts(), propagation_direction="sideways", **kw)
    with pytest.raises(ValueError):  # backward needs a prompt after frame 0
        build_video_request(prompts()[:2], propagation_direction="backward", **kw)
    with pytest.raises(ValueError):  # box outside the frame
        build_video_request([VideoBoxPrompt("a", (0, 0, 100, 5), 0)], **kw)
    with pytest.raises(ValueError):  # same object twice on one frame
        build_video_request([VideoBoxPrompt("a", (0, 0, 5, 5), 0), VideoBoxPrompt("a", (1, 1, 6, 6), 0)], **kw)
    many = [VideoBoxPrompt(f"o{i}", (0, 0, 5, 5), 0) for i in range(17)]
    with pytest.raises(ValueError):
        build_video_request(many, **kw)
    assert len(build_video_request(many[:16], **kw).id_to_label) == 16


def adapter(handler):
    return MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler))


def test_track_success_sends_key_and_returns_frames():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text=sse(delta(F0), delta(F1), completed(60)))

    guard = BudgetGuard(max_calls=1, max_cost_usd=1.0)
    req = build_video_request(prompts(), frame_width=400, frame_height=400, file_id="f")
    result = adapter(handler).track(req, frames=60, budget=guard)
    assert seen["auth"] == f"Bearer {KEY}" and seen["body"]["stream"] is True
    assert len(result.parse.frames) == 2 and result.billed_frames == 60
    assert result.reserved_usd == pytest.approx(0.012) and guard.calls == 1


def test_no_retry_on_http_500_and_key_not_leaked():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500, text=f"boom {KEY}")

    guard = BudgetGuard(max_calls=3, max_cost_usd=1.0)
    req = build_video_request(prompts(), frame_width=400, frame_height=400, file_id="f")
    with pytest.raises(MetaApiError) as err:
        adapter(handler).track(req, frames=60, budget=guard)
    assert len(calls) == 1
    assert KEY not in str(err.value)
    assert guard.calls == 1  # the reservation stands: the request may have been billed


def test_budget_blocks_before_any_request():
    calls = []
    guard = BudgetGuard(max_calls=1, max_cost_usd=0.001)
    req = build_video_request(prompts(), frame_width=400, frame_height=400, file_id="f")
    with pytest.raises(BudgetExceeded):
        adapter(lambda r: calls.append(1)).track(req, frames=60, budget=guard)
    assert calls == []


def test_upload_and_delete_file_use_fake_transport(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fake video bytes")
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.content))
        if request.method == "POST":
            return httpx.Response(200, json={"id": "file-123", "status": "uploaded"})
        return httpx.Response(200, json={"id": "file-123", "deleted": True})

    client = adapter(handler)
    assert client.upload_file(path) == "file-123"
    assert client.delete_file("file-123")["deleted"] is True
    assert seen[0][0:2] == ("POST", "/v1/files")
    assert b"purpose" in seen[0][2] and b"user_data" in seen[0][2]
    assert b"clip.mp4" in seen[0][2] and b"fake video bytes" in seen[0][2]
    assert seen[1][0:2] == ("DELETE", "/v1/files/file-123")


def test_upload_size_cap_is_checked_before_open(tmp_path, monkeypatch):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"too large")
    monkeypatch.setattr("blindspot_ci.providers.sam_video.VIDEO_UPLOAD_MAX_BYTES", 2)
    calls = []
    with pytest.raises(ValueError, match="above"):
        adapter(lambda request: calls.append(request)).upload_file(path)
    assert calls == []
    assert VIDEO_UPLOAD_MAX_BYTES > 0
