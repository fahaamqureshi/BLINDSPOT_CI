import zipfile

import pytest

from blindspot_ci.experiment.mot_importer import build_manifest, parse_gt, select_targets


def _gt_rows(frame_count=301):
    rows = []
    for frame in range(1, frame_count + 1):
        if frame == 10:
            continue
        x, y, width, height, visibility = 100, 100, 100, 100, 0.6
        if frame == 2:
            visibility = 0.4
        elif frame == 3:
            x, y, width, height = 10, 10, 10, 10
        elif frame == 4:
            x = 0
        rows.append(f"{frame},7,{x},{y},{width},{height},1,1,{visibility}")
    return "\n".join(rows) + "\n"


def _labels_zip(tmp_path, frame_count=301, unsafe=False):
    path = tmp_path / "MOT20Labels.zip"
    with zipfile.ZipFile(path, "w") as archive:
        if unsafe:
            archive.writestr("../unsafe.txt", "bad")
        prefix = "MOT20/train/MOT20-02"
        archive.writestr(f"{prefix}/seqinfo.ini", "[Sequence]\nname=MOT20-02\n" f"imDir=img1\nframeRate=25\nseqLength={frame_count}\nimWidth=1000\nimHeight=800\n")
        archive.writestr(f"{prefix}/gt/gt.txt", _gt_rows(frame_count))
    return path


def _preflight(frame_count=301):
    return {
        "labels_archive_sha256": None,
        "sequences": {
            "MOT20-02": {
                "mp4_url": "https://motchallenge.net/sequenceVideos/MOT20-02-raw.mp4",
                "frame_count": frame_count,
                "frame_size": [1000, 800],
                "fps": 25,
                "luminance_samples": [
                    {"frame": 1, "mean_luminance": 100},
                    {"frame": 4, "mean_luminance": 10},
                    {"frame": frame_count, "mean_luminance": 200},
                ],
            }
        },
    }


def test_parse_selection_is_deterministic_and_needs_long_tracks():
    rows = parse_gt("\n".join(f"{frame},3,10,10,100,100,1,1,0.8" for frame in range(1, 301)))
    first = select_targets(rows, (1000, 800))
    second = select_targets(rows, (1000, 800))
    assert [item["track_id"] for item in first] == [3]
    assert first == second
    short = parse_gt("1,4,10,10,100,100,1,1,0.8\n")
    assert select_targets(short, (1000, 800)) == []


def test_manifest_has_seed_box_gaps_and_condition_tags(tmp_path):
    labels = _labels_zip(tmp_path)
    manifest = build_manifest(labels, _preflight(), sequences=("MOT20-02",), max_targets=1)
    target = manifest["sequences"][0]["targets"][0]
    assert target["seed_frame"] == 0 and target["source_seed_frame"] == 1
    assert target["seed_box"] == [100.0, 100.0, 199.0, 199.0]
    frames = {frame["frame"]: frame for frame in target["frames"]}
    assert 0 not in frames and max(frames) == 300
    assert frames[9]["status"] == "NOT_SCORED" and frames[9]["source_frame"] == 10
    assert frames[1]["tags"] == ["occluded"]
    assert frames[2]["tags"] == ["small_object", "dark"]
    assert frames[3]["tags"] == ["truncated", "dark"]
    assert manifest["frame_index_base"] == 0 and not manifest["seed_frames_scored"]


def test_seed_skips_out_of_frame_rows():
    rows = parse_gt(
        "1,8,-2,0,10,10,1,1,0.9\n"
        "2,8,1,1,10,10,1,1,0.4\n"
        "3,8,1,1,10,10,1,1,0.9\n"
        + "\n".join(f"{frame},8,1,1,10,10,1,1,0.9" for frame in range(4, 301))
    )
    assert select_targets(rows, (100, 100))[0]["seed_frame"] == 3


def test_imported_zero_based_seed_and_following_frame_align_with_video_api(tmp_path):
    import httpx

    from blindspot_ci.experiment.temporal import build_sequence_request, run_long_video
    from blindspot_ci.providers.sam_video import MetaSam31VideoAdapter

    manifest = build_manifest(_labels_zip(tmp_path), _preflight(), sequences=("MOT20-02",), max_targets=1)
    request, _ = build_sequence_request(manifest["sequences"][0])
    assert request.body["input"][0]["content"][0]["text"].startswith("<0f>1<|box;")
    response = ('data: {"type":"response.output_text.delta","delta":'
                '"<1f>1<|box;x1=100;y1=100;x2=200;y2=200|>\\n"}\n\n'
                'data: {"type":"response.completed","response":{}}\n\n')
    adapter = MetaSam31VideoAdapter("fake", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=response)))
    report = run_long_video(manifest, ["MOT20-02"], 1,
                            runs_dir=tmp_path / "runs", raw_dir=tmp_path / "raw", adapter=adapter)
    import json

    result = json.loads((tmp_path / "runs" / f"{report['id']}.temporal.json").read_text())
    first = result["sequences"][0]["targets"][0]["frames"][0]
    assert first["frame"] == 1 and first["status"] == "PASS" and first["iou"] == 1


def test_rejects_unsafe_member_and_wrong_frame_count(tmp_path):
    with pytest.raises(ValueError, match="unsafe archive path"):
        build_manifest(_labels_zip(tmp_path, unsafe=True), _preflight(), sequences=("MOT20-02",))
    labels = _labels_zip(tmp_path)
    with pytest.raises(ValueError, match="wrong frame count"):
        build_manifest(labels, _preflight(frame_count=302), sequences=("MOT20-02",))


def test_rejects_malformed_gt(tmp_path):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as archive:
        prefix = "MOT20/train/MOT20-02"
        archive.writestr(f"{prefix}/seqinfo.ini", "[Sequence]\nframeRate=25\nseqLength=301\nimWidth=1000\nimHeight=800\n")
        archive.writestr(f"{prefix}/gt/gt.txt", "1,1,0,0,10\n")
    with pytest.raises(ValueError, match="at least 9"):
        build_manifest(path, _preflight(), sequences=("MOT20-02",))
