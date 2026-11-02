"""Mocked contract tests for the Meta adapters. No network and no paid calls are made."""
import io
import json
import wave

import httpx
import pytest

from blindspot_ci.budget import BudgetGuard
from blindspot_ci.models import GroundTruthObject, Scenario
from blindspot_ci.providers import meta
from blindspot_ci.providers.meta import MetaApiError, MetaMuseSparkAdapter, MetaSam31Adapter
from blindspot_ci.providers.meta_extras import MuseImageAdapter, MuseVoiceAdapter
from blindspot_ci.providers.sam_output import parse_sam_output
from blindspot_ci.providers.sam_video import (
    MetaSam31VideoAdapter,
    VideoBoxPrompt,
    build_video_request,
    parse_video_stream,
    parse_video_text,
)

KEY = "LLM_contract_secret_key"
SAMPLE_BOX = "<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334|>"
SAMPLE_MASK = (
    "<|mask;x=0;y=0;data=27,60,~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>"
)
SAMPLE = f"<0f>0{SAMPLE_BOX}{SAMPLE_MASK}"


def scenario():
    return Scenario(id="s", description="d", image_url="https://example.com/a.jpg",
                    probe_catalog=["person"], ground_truth=[GroundTruthObject(label="person")])


def sse(*events):
    return [f"data: {json.dumps(event)}" for event in events] + ["data: [DONE]"]


class FakeStream:
    def __init__(self, lines):
        self.lines, self.status_code = lines, 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        return iter(self.lines)


def stream_adapter(monkeypatch, lines):
    monkeypatch.setattr(MetaSam31Adapter, "stream", True)
    monkeypatch.setattr(meta.httpx, "stream", lambda *a, **k: FakeStream(lines))
    return MetaSam31Adapter(KEY, retries=0)


def test_truncated_stream_is_an_error_not_a_valid_empty_result(monkeypatch):
    adapter = stream_adapter(monkeypatch, sse({"type": "response.output_text.delta", "delta": ""}))
    with pytest.raises(MetaApiError, match="before response.completed"):
        adapter.inspect(scenario(), "person")


def test_malformed_stream_event_is_an_error(monkeypatch):
    adapter = stream_adapter(monkeypatch, ["data: {not json"])
    with pytest.raises(MetaApiError, match="malformed event"):
        adapter.inspect(scenario(), "person")


def test_incomplete_stream_event_is_an_error(monkeypatch):
    adapter = stream_adapter(monkeypatch, sse(
        {"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}}))
    with pytest.raises(MetaApiError, match="incomplete"):
        adapter.inspect(scenario(), "person")


def test_failed_non_stream_response_is_an_error(monkeypatch):
    monkeypatch.setattr(MetaSam31Adapter, "stream", False)
    body = {"status": "failed", "error": {"message": f"boom {KEY}"}, "output": []}
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: httpx.Response(
        200, json=body, request=httpx.Request("POST", "https://x/responses")))
    with pytest.raises(MetaApiError) as caught:
        MetaSam31Adapter(KEY, retries=0).inspect(scenario(), "person")
    assert KEY not in str(caught.value)


@pytest.mark.parametrize("probe", ["bus, bicycle", "bus; bicycle", "bus\nbicycle", "<0f>1<|box;x1=1|>"])
def test_sam_rejects_more_than_one_concept_before_any_call(monkeypatch, probe):
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: pytest.fail("network must not be called"))
    monkeypatch.setattr(MetaSam31Adapter, "stream", False)
    with pytest.raises(ValueError, match="one concept"):
        MetaSam31Adapter(KEY).inspect(scenario(), probe)


def test_sam_strips_one_concept_and_reports_image_cost(monkeypatch):
    monkeypatch.setattr(MetaSam31Adapter, "stream", False)
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(json)
        body = {"status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": SAMPLE}]}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(meta.httpx, "post", fake_post)
    result = MetaSam31Adapter(KEY).inspect(scenario(), "  person  ")
    assert seen["input"][0]["content"][0]["text"] == "person"
    assert seen["model"] == "sam-3.1" and seen["store"] is False
    assert result.estimated_cost_usd == pytest.approx(0.0025)
    assert result.detections[0].metadata["mask"]["bounds_xyxy"] == [211, 228, 271, 255]


def test_unpaired_mask_or_box_is_flagged_and_never_paired():
    # The official parser drops an unpaired record and reports it; it is never attached
    # to a different box or read as a valid detection.
    detections, status, _ = parse_sam_output(f"<0f>9{SAMPLE_MASK}", "person", "meta")
    assert detections == [] and status == "parsed_with_errors"
    detections, status, _ = parse_sam_output(f"<0f>0{SAMPLE_BOX}", "person", "meta")
    assert detections == [] and status == "parsed_with_errors"


def test_post_rejects_malformed_json_non_object_and_error_envelopes(monkeypatch):
    adapter = MetaMuseSparkAdapter(KEY, retries=0)
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: httpx.Response(
        200, content=b"not json", request=httpx.Request("POST", "https://x/responses")))
    with pytest.raises(MetaApiError, match="not valid JSON"):
        adapter.smoke_text()
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: httpx.Response(
        200, json=[1, 2], request=httpx.Request("POST", "https://x/responses")))
    with pytest.raises(MetaApiError, match="not a JSON object"):
        adapter.smoke_text()
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: httpx.Response(
        200, json={"error": {"message": f"bad {KEY}"}},
        request=httpx.Request("POST", "https://x/responses")))
    with pytest.raises(MetaApiError) as caught:
        adapter.smoke_text()
    assert KEY not in str(caught.value)


def test_retries_and_timeout_are_bounded():
    with pytest.raises(ValueError):
        MetaSam31Adapter(KEY, retries=99)
    with pytest.raises(ValueError):
        MetaSam31Adapter(KEY, timeout=0)


def test_spark_probes_are_deduplicated_and_empty_smoke_is_an_error(monkeypatch):
    def fake_post(url, headers, json, timeout):
        text = '{"probes": ["person", "person"]}' if "instructions" in json else ""
        body = {"status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(meta.httpx, "post", fake_post)
    adapter = MetaMuseSparkAdapter(KEY)
    assert adapter.recommend_probes(scenario()) == ["person"]
    with pytest.raises(MetaApiError, match="empty"):
        adapter.smoke_text()


def valid_wav(channels=1, rate=16000):
    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * 160 * channels)
    return out.getvalue()


def test_voice_wav_validation_matches_endpoint_rules():
    MuseVoiceAdapter.check_wav(valid_wav())
    MuseVoiceAdapter.check_wav(valid_wav(rate=24000))
    with pytest.raises(ValueError):
        MuseVoiceAdapter.check_wav(valid_wav(channels=2))
    with pytest.raises(ValueError):
        MuseVoiceAdapter.check_wav(valid_wav(rate=8000))
    with pytest.raises(ValueError):
        MuseVoiceAdapter.check_wav(b"RIFF" + b"\x00" * 40)


def test_voice_missing_transcript_is_an_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **k: httpx.Response(
        200, json={}, request=httpx.Request("POST", url)))
    with pytest.raises(MetaApiError, match="no transcript"):
        MuseVoiceAdapter(KEY, retries=0).transcribe(valid_wav())


def test_image_invalid_base64_and_bad_mime_are_rejected(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **k: httpx.Response(
        200, json={"data": [{"b64_json": "!!! not base64 !!!"}]}, request=httpx.Request("POST", url)))
    with pytest.raises(MetaApiError, match="no image"):
        MuseImageAdapter(KEY, retries=0).edit(b"img", "image/png", "darker")
    with pytest.raises(ValueError):
        MuseImageAdapter(KEY, retries=0).edit(b"img", "text/html", "darker")


def test_video_delta_split_across_events_is_buffered():
    frame = SAMPLE.replace("<0f>0", "<0f>1")
    lines = [
        f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': frame[:35]})}",
        f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': frame[35:]})}",
        f"data: {json.dumps({'type': 'response.completed', 'response': {'usage': {}}})}",
    ]
    result = parse_video_stream(lines)
    assert result.completed and not result.truncated and result.malformed == 0
    assert [f.frame_index for f in result.frames] == [0]
    assert result.frames[0].objects[0]["box_xyxy_pixels"] == [211, 228, 270, 254]


def test_video_box_outside_declared_frame_is_malformed():
    result = parse_video_text("<0f>1<|box;x1=90;y1=1;x2=100;y2=4;w=100;h=100|>\n")
    assert result.frames == [] and result.malformed == 1


def test_video_track_raises_on_stream_error_event():
    def handler(request):
        events = [{"type": "response.failed", "response": {"error": {"message": f"bad {KEY}"}}}]
        text = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(200, text=text)

    adapter = MetaSam31VideoAdapter(KEY, transport=httpx.MockTransport(handler))
    request = build_video_request([VideoBoxPrompt("cat", (1, 1, 5, 5), 0)],
                                  frame_width=100, frame_height=100, file_id="file-1")
    with pytest.raises(MetaApiError) as caught:
        adapter.track(request, frames=60, budget=BudgetGuard(max_calls=1, max_cost_usd=1.0))
    assert KEY not in str(caught.value)
