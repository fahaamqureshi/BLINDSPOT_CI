import httpx
import pytest

from blindspot_ci.agent import BlindspotAgent
from blindspot_ci.cache import JsonCache
from blindspot_ci.models import GroundTruthObject, Scenario
from blindspot_ci.provenance import ProvenanceLog
from blindspot_ci.providers import meta
from blindspot_ci.providers.meta import MetaApiError, MetaSam31Adapter
from blindspot_ci.providers.sam_output import parse_sam_output

# Sample output copied from the official meta-sam-parser README.
SAMPLE = (
    "<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334|>"
    "<|mask;x=0;y=0;data=27,60,~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>"
    ",1<|box;x1=155;y1=228;x2=202;y2=254;w=320;h=334|>"
    "<|mask;x=0;y=0;data=27,48,~!!!!J!0c[q=Pj_zs=*4C4(/./x#:/`S_GnD`=o3?X{emCgO$y@|>\n"
)


@pytest.fixture(autouse=True)
def non_streaming_by_default(monkeypatch):
    monkeypatch.setattr(MetaSam31Adapter, "stream", False)


def scenario(url="https://example.com/a.jpg"):
    return Scenario(id="s", description="d", image_url=url, probe_catalog=["person"],
                    ground_truth=[GroundTruthObject(label="person", severity="high")])


def fake_response(text, status=200):
    body = {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 5, "output_tokens": 7}}
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x/responses"))


def test_parser_reads_official_sample():
    detections, status, _ = parse_sam_output(SAMPLE, "person", "meta")
    assert status == "structured"
    assert [d.label for d in detections] == ["person", "person"]
    assert detections[0].metadata["box_xyxy"] == [211, 228, 271, 255]
    assert detections[0].confidence is None  # sample has no c field; never invented
    assert detections[0].metadata["mask"]["width"] == 60


def test_empty_output_is_a_valid_no_match():
    assert parse_sam_output("", "person", "meta") == ([], "structured", [])


def test_plain_text_is_flagged_not_trusted():
    detections, status, _ = parse_sam_output("I see a person.", "person", "meta")
    assert detections == [] and status == "unparsed_text"


def test_malformed_record_is_flagged():
    _, status, _ = parse_sam_output("<0f>\n", "person", "meta")
    assert status == "parsed_with_errors"


def test_adapter_request_and_parse(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, auth=headers["Authorization"], body=json)
        return fake_response(SAMPLE)

    monkeypatch.setattr(meta.httpx, "post", fake_post)
    result = MetaSam31Adapter("k-test", "https://api.meta.ai/v1").inspect(scenario(), "person")
    assert sent["url"] == "https://api.meta.ai/v1/responses"
    assert sent["body"]["model"] == "sam-3.1" and sent["body"]["store"] is False
    assert len(result.detections) == 2 and result.parser_status == "structured"
    assert result.usage["output_tokens"] == 7


def test_adapter_rejects_missing_key_and_unsafe_urls():
    with pytest.raises(ValueError):
        MetaSam31Adapter("")
    adapter = MetaSam31Adapter("k")
    with pytest.raises(ValueError):
        adapter.inspect(scenario(None), "person")
    with pytest.raises(ValueError):
        adapter.inspect(scenario("file:///C:/secret.png"), "person")


def test_adapter_retries_rate_limit(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "0"}, json={}) if len(calls) == 1 \
            else fake_response("")

    monkeypatch.setattr(meta.httpx, "post", fake_post)
    monkeypatch.setattr(meta.time, "sleep", lambda s: None)
    assert MetaSam31Adapter("k").inspect(scenario(), "person").parser_status == "structured"
    assert len(calls) == 2


def test_agent_survives_provider_error_and_keeps_provenance(monkeypatch, tmp_path):
    def boom(url, headers, json, timeout):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(meta.httpx, "post", boom)
    agent = BlindspotAgent(MetaSam31Adapter("k", retries=0), JsonCache(tmp_path / "c"),
                           ProvenanceLog(tmp_path / "p.jsonl"))
    report = agent.run(scenario())
    assert report.status == "needs_human_review"
    assert any("provider error" in r for r in report.review_reasons)
    assert "provider_error" in (tmp_path / "p.jsonl").read_text(encoding="utf-8")
    assert not any((tmp_path / "c").iterdir())  # failures are never cached


def test_unparsed_live_output_forces_review(monkeypatch, tmp_path):
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: fake_response("a person is here"))
    agent = BlindspotAgent(MetaSam31Adapter("k"), JsonCache(tmp_path / "c"), ProvenanceLog(tmp_path / "p.jsonl"))
    assert "not parsed" in " ".join(agent.run(scenario()).review_reasons)


def test_meta_api_error_type():
    assert issubclass(MetaApiError, RuntimeError)


def test_error_shows_server_message_and_redacts_key(monkeypatch):
    def not_found(url, headers, json, timeout):
        request = httpx.Request("POST", url)
        return httpx.Response(404, text='{"error":"model nope for key SECRET-KEY-123"}', request=request)

    monkeypatch.setattr(meta.httpx, "post", not_found)
    with pytest.raises(MetaApiError) as info:
        MetaSam31Adapter("SECRET-KEY-123", retries=0).inspect(scenario(), "person")
    message = str(info.value)
    assert "404" in message and "server said" in message and "SECRET-KEY-123" not in message



class FakeStream:
    def __init__(self, lines, status=200):
        self.lines, self.status_code = lines, status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        return iter(self.lines)

    def read(self):
        return b""

    def raise_for_status(self):
        raise httpx.HTTPStatusError(f"Client error {self.status_code}", request=httpx.Request("POST", "https://x"),
                                    response=httpx.Response(self.status_code, text="nope"))


def sse(*events):
    import json as _json
    return [f"data: {_json.dumps(e)}" for e in events] + ["data: [DONE]"]


def test_streaming_collects_text_and_usage(monkeypatch):
    monkeypatch.setattr(MetaSam31Adapter, "stream", True)
    seen = {}

    def fake_stream(method, url, headers, json, timeout):
        seen["body"] = json
        return FakeStream(sse(
            {"type": "response.content_part.done", "output_index": 0, "content_index": 0,
             "part": {"type": "output_text", "text": SAMPLE}},
            {"type": "response.completed", "response": {"usage": {"output_tokens": 9}}}))

    monkeypatch.setattr(meta.httpx, "stream", fake_stream)
    result = MetaSam31Adapter("k").inspect(scenario(), "person")
    assert seen["body"]["stream"] is True
    assert len(result.detections) == 2 and result.usage == {"output_tokens": 9}


def test_streaming_failure_event_raises_and_redacts(monkeypatch):
    monkeypatch.setattr(MetaSam31Adapter, "stream", True)
    monkeypatch.setattr(meta.httpx, "stream", lambda *a, **k: FakeStream(sse(
        {"type": "response.failed", "response": {"error": {"message": "bad key KKK"}}})))
    with pytest.raises(MetaApiError) as info:
        MetaSam31Adapter("KKK").inspect(scenario(), "person")
    assert "KKK" not in str(info.value) and "failed" in str(info.value)


def test_streaming_http_error_includes_server_message(monkeypatch):
    monkeypatch.setattr(MetaSam31Adapter, "stream", True)
    monkeypatch.setattr(meta.httpx, "stream", lambda *a, **k: FakeStream([], status=400))
    with pytest.raises(MetaApiError) as info:
        MetaSam31Adapter("k", retries=0).inspect(scenario(), "person")
    assert "400" in str(info.value) and "nope" in str(info.value)



def test_data_url_images_are_accepted_and_other_schemes_rejected(monkeypatch):
    from blindspot_ci.media import file_to_data_url

    seen = {}

    def fake_post(url, headers, json, timeout):
        seen["image"] = json["input"][0]["content"][1]["image_url"]
        return fake_response("")

    monkeypatch.setattr(meta.httpx, "post", fake_post)
    adapter = MetaSam31Adapter("k")
    adapter.inspect(scenario("data:image/png;base64,AAAA"), "person")
    assert seen["image"].startswith("data:image/png;base64,")
    for bad in ["http://example.com/a.jpg", "data:text/html;base64,AAAA", "file:///C:/a.png"]:
        with pytest.raises(ValueError):
            adapter.inspect(scenario(bad), "person")
    assert file_to_data_url  # imported for the file tests below


def test_file_to_data_url(tmp_path):
    from blindspot_ci.media import file_to_data_url

    good = tmp_path / "a.JPG"
    good.write_bytes(b"\xff\xd8\xff")
    assert file_to_data_url(good).startswith("data:image/jpeg;base64,")
    with pytest.raises(ValueError):
        file_to_data_url(tmp_path / "missing.png")
    bad = tmp_path / "a.gif"
    bad.write_bytes(b"x")
    with pytest.raises(ValueError):
        file_to_data_url(bad)
    big = tmp_path / "big.png"
    big.write_bytes(b"x" * 4_000_001)
    with pytest.raises(ValueError):
        file_to_data_url(big)


def test_cache_key_changes_with_image(tmp_path):
    from blindspot_ci.providers.mock import MockVisionProvider

    agent = BlindspotAgent(MockVisionProvider({"s": {"person": {"confidence": 0.9}}}),
                           JsonCache(tmp_path / "c"), ProvenanceLog(tmp_path / "p.jsonl"))
    agent.run(scenario("https://example.com/one.jpg"))
    second = agent.run(scenario("https://example.com/two.jpg"))
    assert not second.results[0].cache_hit


@pytest.mark.parametrize("reply, expect_ok", [
    ('{"probes": ["person"]}', True),
    ('```json\n{"probes": ["person"]}\n```', True),
    ("not json at all", False),
    ('{"probes": ["nothing_real"]}', False),
])
def test_recommend_probes_is_strict(monkeypatch, reply, expect_ok):
    monkeypatch.setattr(meta.httpx, "post", lambda *a, **k: fake_response(reply))
    adapter = meta.MetaMuseSparkAdapter("k")
    if expect_ok:
        assert adapter.recommend_probes(scenario()) == ["person"]
    else:
        with pytest.raises(ValueError):
            adapter.recommend_probes(scenario())


def test_client_errors_are_not_retried_and_bad_retry_after_is_safe():
    import httpx

    from blindspot_ci.providers.meta import _MetaBase

    request = httpx.Request("POST", "https://example.invalid")
    for code, retry in [(400, False), (401, False), (404, False), (429, True), (503, True)]:
        exc = httpx.HTTPStatusError("x", request=request, response=httpx.Response(code, request=request))
        assert _MetaBase._not_retryable(exc) is (not retry), code
    assert _MetaBase._retry_delay("Wed, 21 Oct 2026 07:28:00 GMT", 0) < 1.0
    assert _MetaBase._retry_delay("3", 0) == 3.0


def test_build_agent_respects_the_live_switch(monkeypatch):
    import dataclasses

    from blindspot_ci.config import Settings
    from blindspot_ci.factory import build_agent

    cfg = dataclasses.replace(Settings(), provider="meta", live_api_enabled=False, model_api_key="LLM_x_y")
    with pytest.raises(PermissionError):
        build_agent(cfg)
