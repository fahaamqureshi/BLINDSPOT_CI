import base64
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from blindspot_ci import factory
from blindspot_ci.api import app
from blindspot_ci.budget import BudgetExceeded, BudgetGuard
from blindspot_ci.experiment import stress
from blindspot_ci.experiment.cases import load_dataset, load_named_dataset
from blindspot_ci.providers import meta_extras
from blindspot_ci.providers.meta import MetaApiError
from blindspot_ci.providers.meta_extras import (
    MuseImageAdapter,
    MuseVoiceAdapter,
    MuseWonderAuditor,
    audit_input,
)

KEY = "LLM_test_key_value"


def png_bytes(size=(40, 30)):
    out = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(out, "PNG")
    return out.getvalue()


def wav_bytes():
    import wave

    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 160)
    return out.getvalue()


def fake_post(monkeypatch, body, status=200, seen=None):
    def post(url, **kwargs):
        if seen is not None:
            seen.update(url=url, **kwargs)
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)


def test_image_adapter_sends_json_edit_and_decodes(monkeypatch):
    seen = {}
    fake_post(monkeypatch, {"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]}, seen=seen)
    assert MuseImageAdapter(KEY).edit(b"img", "image/png", "darker") == b"PNGDATA"
    assert seen["url"].endswith("/images/edits")
    assert seen["json"]["model"] == "muse-image-1.0" and seen["json"]["output_format"] == "png"
    assert seen["json"]["images"][0]["image_url"].startswith("data:image/png;base64,")
    assert KEY not in json.dumps(seen["json"])


def test_image_adapter_rejects_reply_without_image(monkeypatch):
    fake_post(monkeypatch, {"data": []})
    with pytest.raises(MetaApiError):
        MuseImageAdapter(KEY).edit(b"img", "image/png", "x")


def test_voice_adapter_posts_multipart_and_reads_transcript(monkeypatch):
    seen = {}
    fake_post(monkeypatch, {"transcript": " tag is visible "}, seen=seen)
    assert MuseVoiceAdapter(KEY).transcribe(wav_bytes()) == "tag is visible"
    assert seen["url"].endswith("/asr/transcribe")
    request = json.loads(seen["files"]["request"][1])
    assert request["audioEncoding"] == "WAV" and request["model"] == "muse-voice-transcribe-1.0"


def test_voice_adapter_refuses_non_wav():
    with pytest.raises(ValueError):
        MuseVoiceAdapter(KEY).transcribe(b"not audio at all")


def test_wonder_auditor_uses_chat_completions(monkeypatch):
    seen = {}
    fake_post(monkeypatch, {"choices": [{"message": {"content": "  audit text "}}]}, seen=seen)
    assert MuseWonderAuditor(KEY).audit({"steps": []}) == "audit text"
    assert seen["url"].endswith("/chat/completions") and seen["json"]["model"] == "muse-wonder-1.0"


def test_wonder_empty_reply_is_an_error(monkeypatch):
    fake_post(monkeypatch, {"choices": [{"message": {"content": ""}}]})
    with pytest.raises(MetaApiError):
        MuseWonderAuditor(KEY).audit({})


def test_error_text_redacts_the_key(monkeypatch):
    fake_post(monkeypatch, {"error": f"bad {KEY}"}, status=400)
    with pytest.raises(MetaApiError) as err:
        MuseImageAdapter(KEY).edit(b"i", "image/png", "x")
    assert KEY not in str(err.value)


class FakeImage:
    model = "muse-image-1.0"

    def __init__(self, size=(40, 30)):
        self.calls, self.size = 0, size

    def edit(self, image_bytes, mime, prompt):
        self.calls += 1
        return png_bytes(self.size)


@pytest.fixture
def source(tmp_path):
    (tmp_path / "real").mkdir()
    Image.new("RGB", (100, 80), (200, 200, 200)).save(tmp_path / "real" / "a.png")
    Image.new("RGB", (100, 80), (200, 200, 200)).save(tmp_path / "real" / "b.png")
    manifest = {"dataset_id": "t", "type": "HUMAN_LABELED_REAL_PHOTOS", "cases": [
        {"id": "case_a", "title": "A", "image": "real/a.png", "condition": "normal", "concept": "tag",
         "ground_truth": {"visibility": "visible", "bbox": [10, 10, 50, 40]}, "label_provenance": {"annotator": "me"}},
        {"id": "case_b", "title": "B", "image": "real/b.png", "condition": "absent", "concept": "tag",
         "ground_truth": {"visibility": "absent", "bbox": None}}]}
    path = tmp_path / "m.json"
    path.write_text(json.dumps(manifest))
    return load_dataset(path, tmp_path), tmp_path


def test_variants_inherit_box_are_marked_and_resized(source):
    dataset, base = source
    fake = FakeImage(size=(40, 30))  # model returned a different resolution
    entries = stress.generate_variants(dataset, ["low_light", "glare"], fake, BudgetGuard(10, 1.0), datasets=base)
    assert fake.calls == 2 and [e["id"] for e in entries] == ["case_a_low_light", "case_a_glare"]  # absent skipped
    assert all(e["ground_truth"]["bbox"] == [10, 10, 50, 40] for e in entries)
    prov = entries[0]["label_provenance"]
    assert prov["box_status"] == "inherited_from_source_not_reverified" and prov["generator"] == "muse-image-1.0"
    with Image.open(base / "generated" / "case_a_glare.png") as made:
        assert made.size == (100, 80)
    path = stress.write_manifest(entries, dataset, base)
    loaded = load_dataset(path, base)  # passes box and hash validation
    assert loaded.kind.startswith("GENERATED") and len(loaded.cases) == 2


def test_variants_respect_limits_and_budget(source):
    dataset, base = source
    with pytest.raises(ValueError):
        stress.generate_variants(dataset, ["nope"], FakeImage(), BudgetGuard(10, 1.0), datasets=base)
    with pytest.raises(ValueError):
        stress.generate_variants(dataset, ["low_light"], FakeImage(), BudgetGuard(10, 1.0), ["case_b"], base)
    with pytest.raises(BudgetExceeded):
        stress.generate_variants(dataset, ["low_light", "glare"], FakeImage(), BudgetGuard(10, 0.015), datasets=base)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINDSPOT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.delenv("LIVE_API_ENABLED", raising=False)
    return TestClient(app)


@pytest.fixture
def run_id(client):
    return client.post("/api/experiment", json={"max_steps": 2}).json()["id"]


def test_new_endpoints_are_refused_without_live_switch(client, run_id):
    assert client.post("/api/stress", json={"source": "synthetic", "edits": ["low_light"]}).status_code == 403
    assert client.post(f"/api/runs/{run_id}/audit").status_code == 403
    assert client.post(f"/api/runs/{run_id}/voice?case_id=normal", content=wav_bytes()).status_code == 403


def test_typed_note_is_saved_and_returned_with_run(client, run_id):
    case = client.get(f"/api/runs/{run_id}").json()["steps"][0]["case"]["id"]
    ok = client.post(f"/api/runs/{run_id}/notes", json={"case_id": case, "text": "box looks right"})
    assert ok.status_code == 200 and ok.json()["source"] == "typed"
    assert client.get(f"/api/runs/{run_id}").json()["reviewer_notes"][0]["text"] == "box looks right"
    assert client.post(f"/api/runs/{run_id}/notes", json={"case_id": "ghost", "text": "x"}).status_code == 422
    assert client.post("/api/runs/not-a-run/notes", json={"case_id": case, "text": "x"}).status_code == 404


def test_voice_audit_and_stress_endpoints_with_fakes(client, run_id, monkeypatch):
    class Voice:
        model = "v"
        def transcribe(self, wav): return "spoken verdict"

    class Auditor:
        model = "w"
        def audit(self, summary): return "AUDIT " + json.dumps(summary)[:20]

    monkeypatch.setenv("LIVE_API_ENABLED", "true")
    monkeypatch.setattr(factory, "build_voice_adapter", lambda *a: Voice())
    monkeypatch.setattr(factory, "build_wonder_auditor", lambda *a: Auditor())
    case = client.get(f"/api/runs/{run_id}").json()["steps"][0]["case"]["id"]
    note = client.post(f"/api/runs/{run_id}/voice?case_id={case}", content=wav_bytes()).json()
    assert note["text"] == "spoken verdict" and note["source"] == "MUSE_VOICE_TRANSCRIBE"
    audit = client.post(f"/api/runs/{run_id}/audit").json()
    assert audit["text"].startswith("AUDIT") and "does not change any score" in audit["note"]
    again = client.get(f"/api/runs/{run_id}").json()
    assert again["audit"]["model"] == "w" and again["summary"]["tested"] == 2  # scores untouched


def test_audit_input_drops_masks_and_keeps_scores():
    run = {"mode": "LIVE_META", "dataset": {"type": "X"}, "min_iou": 0.35, "summary": {"passed": 0},
           "steps": [{"case": {"id": "a", "condition": "normal"}, "decision": {"reason": "r"},
                      "outcome": {"status": "FAIL_FALSE_NEGATIVE", "iou": 0.0},
                      "ground_truth": {"bbox": [1, 2, 3, 4], "visibility": "visible"},
                      "prediction": {"source": "LIVE_META", "detections": [{"bbox": None, "mask": {"svg_path": "BIG"}}]}}]}
    text = json.dumps(audit_input(run))
    assert "BIG" not in text and "FAIL_FALSE_NEGATIVE" in text


def test_models_listed_and_unknown_dataset_rejected(client):
    info = client.get("/api/info").json()
    assert len(info["models"]) == 5 and "synthetic" in info["datasets"]
    assert client.get("/api/cases?dataset=bogus").status_code == 422


def test_constants_match_published_prices():
    assert meta_extras.IMAGE_COST_USD == 0.01 and meta_extras.VOICE_COST_PER_MIN_USD == 0.003
    assert load_named_dataset("synthetic").cases


def test_voice_upload_over_limit_is_refused(client, run_id, monkeypatch):
    class Voice:
        model = "v"
        def transcribe(self, wav): raise AssertionError("must not be called")

    monkeypatch.setenv("LIVE_API_ENABLED", "true")
    monkeypatch.setattr(factory, "build_voice_adapter", lambda *a: Voice())
    monkeypatch.setattr("blindspot_ci.api.MAX_WAV_BYTES", 100)
    case = client.get(f"/api/runs/{run_id}").json()["steps"][0]["case"]["id"]
    assert client.post(f"/api/runs/{run_id}/voice?case_id={case}", content=wav_bytes() + b"x" * 200).status_code == 413


def test_session_budget_caps_repeated_paid_calls(client, run_id, monkeypatch):
    class Auditor:
        model = "w"
        def audit(self, summary): return "ok"

    monkeypatch.setenv("LIVE_API_ENABLED", "true")
    monkeypatch.setattr(factory, "build_wonder_auditor", lambda *a: Auditor())
    monkeypatch.setattr("blindspot_ci.api._SESSION", BudgetGuard(max_calls=100, max_cost_usd=0.05))
    codes = [client.post(f"/api/runs/{run_id}/audit").status_code for _ in range(3)]
    assert codes == [200, 422, 422]  # the second call would pass $0.05 at $0.03 each


# ---- research-driven additions: corruptions, evaluation card, agent baseline ----

def test_corruptions_keep_labels_exact_and_are_deterministic(source):
    from blindspot_ci.experiment.corruptions import CORRUPTIONS, generate_corruptions

    dataset, base = source
    first = generate_corruptions(dataset, list(CORRUPTIONS), [2], datasets=base)
    assert len(first) == 2 * len(CORRUPTIONS)  # the visible case and the absent case both get every corruption
    visible = [e for e in first if e["label_provenance"]["derived_from"] == "case_a"]
    assert all(e["ground_truth"]["bbox"] == [10, 10, 50, 40] for e in visible)
    absent = [e for e in first if e["label_provenance"]["derived_from"] == "case_b"]
    assert all(e["ground_truth"] == {"visibility": "absent", "bbox": None} for e in absent)
    second = generate_corruptions(dataset, list(CORRUPTIONS), [2], datasets=base)
    assert [e["image_sha256"] for e in first] == [e["image_sha256"] for e in second]
    with Image.open(base / "corrupted" / "case_a_blur_s2.jpg") as made:
        assert made.size == (100, 80)  # no resize, no crop: the box stays exact


def test_corruption_severity_actually_degrades(source):
    from blindspot_ci.experiment.corruptions import generate_corruptions

    dataset, base = source
    entries = generate_corruptions(dataset, ["low_light"], [1, 5], ["case_a"], datasets=base)
    means = []
    for e in entries:
        with Image.open(base / e["image"]) as img:
            means.append(sum(img.convert("L").getdata()) / (img.width * img.height))
    assert means[1] < means[0] < 200


def test_corruption_limits_and_endpoint(source, client):
    from blindspot_ci.experiment.corruptions import generate_corruptions

    dataset, base = source
    with pytest.raises(ValueError):
        generate_corruptions(dataset, ["nope"], [1], datasets=base)
    with pytest.raises(ValueError):
        generate_corruptions(dataset, ["blur"], [9], datasets=base)
    assert client.post("/api/corrupt", json={"source": "generated", "corruptions": ["blur"]}).status_code in (404, 422)


def test_card_has_intervals_flags_and_no_forbidden_characters(client, run_id):
    text = client.get(f"/api/runs/{run_id}/card")
    assert text.status_code == 200 and "attachment" in text.headers["content-disposition"]
    body = text.text
    assert "scripted mock answers" in body and "plumbing check" in body  # mock + synthetic are flagged
    assert ("95%" in body or "95 percent" in body) and "underpowered" in body
    assert "not a safety approval" in body
    for bad in ("—", "…", "*"):
        assert bad not in body
    assert client.get("/api/runs/not-a-run/card").status_code == 404


def _card_run(planner):
    run = {
        "id": "a" * 16, "mode": "LIVE_META", "model": "sam-3.1",
        "started_at": "2026-01-01T00:00:00Z", "calls": 0, "estimated_cost_usd": 0.0,
        "min_iou": 0.35,
        "dataset": {"id": "test", "type": "HUMAN_LABELED_REAL_PHOTOS", "annotation_status": "person"},
        "summary": {"tested": 0, "passed": 0, "failed": 0, "unknown": 0, "errors": 0, "scored": 0,
                    "underpowered": True, "by_condition": {}},
        "steps": [], "errors": [],
    }
    if planner is not None:
        run["planner"] = planner
    return run


def test_card_for_scripted_mock_run_does_not_credit_muse(client, run_id):
    body = client.get(f"/api/runs/{run_id}/card").text
    assert "Planner: MOCK_POLICY" in body
    assert "Tests followed a fixed scripted order from a simulated mock planner." in body
    assert "Muse Spark" not in body


def test_card_for_muse_planner_run_credits_muse_spark():
    from blindspot_ci.experiment.card import build_card

    body = build_card(_card_run("MUSE_SPARK_AGENT"))
    assert "Planner: MUSE_SPARK_AGENT" in body
    assert "A Muse Spark agent picks each test by function calling and sees earlier results." in body


def test_card_without_a_recorded_planner_uses_neutral_wording():
    from blindspot_ci.experiment.card import build_card

    body = build_card(_card_run(None))
    assert "Planner: not recorded" in body
    assert "Test order recorded in the run was used." in body
    assert "Muse Spark" not in body


def test_card_for_heuristic_run_does_not_credit_muse():
    from blindspot_ci.experiment.card import build_card

    body = build_card(_card_run("heuristic"))
    assert "Tests followed a heuristic order set by plain Python rules." in body
    assert "Muse Spark" not in body


def test_hypergeometric_baseline_matches_hand_calculation():
    from blindspot_ci.experiment.baseline import compare_to_random

    # 10 cases, 4 failures, agent ran 3 tests and found 2. P(X>=2) = (C(4,2)C(6,1)+C(4,3)C(6,0))/C(10,3)
    result = compare_to_random([True, False, True], 10, 4)
    assert result["p_random_finds_at_least_as_many"] == round((6 * 6 + 4) / 120, 4)
    assert result["random_expected_found"] == 1.2 and result["agent_first_failure_at"] == 1
    assert result["random_expected_first_failure_at"] == 2.2
    with pytest.raises(ValueError):
        compare_to_random([True, True], 10, 1)


def test_partial_variants_survive_a_later_failure(source):
    dataset, base = source

    class Flaky(FakeImage):
        def edit(self, image_bytes, mime, instruction):
            if self.calls >= 1:
                raise MetaApiError("second call failed")
            return super().edit(image_bytes, mime, instruction)

    with pytest.raises(MetaApiError) as caught:
        stress.generate_variants(dataset, ["low_light", "glare"], Flaky(), BudgetGuard(10, 1.0), datasets=base)
    assert [e["id"] for e in caught.value.partial_entries] == ["case_a_low_light"]


def test_run_mode_says_cache_when_every_step_was_replayed(client):
    first = client.post("/api/experiment", json={"max_steps": 2}).json()
    second = client.post("/api/experiment", json={"max_steps": 2}).json()
    assert first["mode"] == "MOCK_FIXTURE" and second["mode"] == "CACHE_MOCK_FIXTURE"
