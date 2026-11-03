# New open-media live demonstration

Date: 2026-11-03. Branch: codex/open-media-live-demo. Baseline: 8dfed9d8771ae969cbc82e9645c071bb3cae124d.

The user explicitly authorized overriding mock-only execution for this test with a USD 0.10 maximum, then authorized the app to load the existing local dotenv credential internally. No key was printed or written to the results. These exceptions apply to this demonstration, not future runs. The normal app configuration and repository rules were not changed.

## Sources and files

Newly downloaded media comes from the [Xiph test-media collection](https://media.xiph.org/video/derf/), which identifies Johnny as public domain.

- [Portrait thumbnail](https://media.xiph.org/video/derf/thumbnails/Johnny_1280x720_60-0001.jpg): saved as artifacts/open-media-demo/johnny.jpg, 10,019 bytes.
- [Johnny source video](https://media.xiph.org/video/derf/webm/Johnny_1280x720_60.webm): saved as johnny.webm, 6,654,698 bytes.
- sources.json in the same directory records URLs, rights statements, sizes and SHA-256 hashes.

These are real photographic/video inputs downloaded for this run, not synthetic fixture answers. They are old public test media, not post-release evidence or proof of clean training separation. Kaggle login was not needed.

Wikimedia offered a CC0 park stop-sign photograph and pedestrian video, but their media download URLs returned HTTP 403 here. No access restriction was bypassed. The alternative public-domain source was downloaded successfully.

## Actual inference

| Input | Actual result | Latency | Usage and estimated cost |
| --- | --- | --- | --- |
| New portrait, prompt person | SAM 3.1 structured output, nine returned detections | 3507 ms | images_processed 1; USD 0.0025 |
| Two-second MP4 excerpt, prompt person | 48 unique frame records, no missing frames, zero malformed records; eight to nine boxes per frame | 5880 ms | video_frames_processed 50; USD 0.0100 |

The input video was genuinely excerpted from the downloaded source, resized to 640 by 360 and sampled at 24 fps, capped at 48 frames. It was not generated. Source and output frames are retained locally. A modern local decoder was installed as imageio-ffmpeg because the preexisting 2013 decoder could not decode VP9.

An initial WebM request returned HTTP 400 with the service message that MP4 is required. The failure is saved as live-video-rejected-webm.json. The same excerpt was converted to MP4 and one corrected request succeeded. There were three total request attempts including that rejection, with automatic retries disabled. No Muse request or background paid job was started.

Successful published-price usage totals USD 0.0125. This is a price-based calculation from returned usage, not an independently verified invoice. Even reserving USD 0.024 for the rejected WebM request, the conservative planned total was USD 0.0365, below the authorized USD 0.10. Pricing was checked against the [official Meta pricing page](https://dev.meta.ai/docs/pricing-rate-limits): USD 2.50 per thousand images and USD 0.20 per thousand video frames, with a 50-frame video minimum.

No independent human box or mask labels were supplied. Accuracy, precision, recall, IoU against ground truth and release readiness are NOT_SCORED. Several background regions depict people, so detection counts alone do not establish correctness. A language model did not create evaluation labels.

## Playable evidence

Open http://127.0.0.1:8020/live-demo.html while its loopback report server is running. The page displays actual image boxes and a playable MP4 with synchronized per-frame boxes. It is a read-only local report, separate from the mock application, and makes no model calls when viewed.

Local artifacts include live-image-result.json, live-video-result.json, live-video-rejected-webm.json, johnny-2s.mp4, video-frame.jpg, live-demo.html, live-image-proof.png and live-video-proof.png. Video overlays use the returned frame_size for coordinate alignment. Browser verified video readyState 4, actual dimensions 640 by 360, and the frame-zero overlay with eight predicted boxes.

The still/video response data and raw segmentation output are retained locally, with no authorization headers or credentials. Media and outputs remain under ignored artifacts and are not committed or packaged. Only this evidence note changes the repository. No push, deployment or submission occurred.

## Verification

The final repository gate uses mock mode, not another paid call:

```text
PASS  ruff
PASS  pytest
PASS  docs style
PASS  attribution
PASS  secrets

Summary: PASS
```

Open work: a person must label the new inputs before accuracy can be scored. This small inference demonstration is not a deployment evaluation. The normal web app remains in mock mode.
