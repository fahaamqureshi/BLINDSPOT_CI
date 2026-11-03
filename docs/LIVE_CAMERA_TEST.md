# Three-minute public camera observation

This was an authorized live test, separate from the normal mock-only release checks. The user authorized three minutes of public camera monitoring. The existing app loaded credentials privately in the isolated worker. No credential was printed or placed in the delivered demo. No project-wide live spending or credential policy was changed.

## Evidence

The source was City of Austin camera 2 at Airport Blvd / Oak Springs Dr. The official image service publishes intermittent public snapshots. This was not continuous video.

- Capture start: 2026-11-03T11:54:15.138329+00:00 UTC.
- Capture end: 2026-11-03T11:57:15.140218+00:00 UTC.
- Measured acquisition window: 180.0 seconds.
- Snapshots requested and saved: 18, at roughly ten-second intervals.
- Distinct image hashes: 2. Repeated images: 16.
- First image publication age: 298.0 seconds. Flagged stale over 180 seconds.
- Later publication ages: 6.8 to 166.7 seconds.
- Muse Spark 1.3 selected traffic light from the bounded catalog car, traffic light, person.
- SAM 3.1 completed two inspections of distinct images. Each returned two traffic-light boxes with structured parser status.
- SAM response times: 2.814 and 2.497 seconds.
- Muse Wonder 1.0 completed the observation report from recorded outputs and source metadata.
- Total model requests: 4, all completed. No automatic retries or automatic restart.
- Human reference labels: none. Scoring status: NOT_SCORED.

SAM image estimates total USD 0.005. This excludes planner and report generation. Planner and report token usage was not returned by these adapter methods, so no exact total invoice is claimed.

## Viewing the result

The prepared demo folder is C:/Users/faham/Downloads/BLINDSPOT_JUDGE_DEMO_2026-11-03. Its portal now includes Public camera test. The recording server serves it at http://127.0.0.1:8050/judge-demo/camera-monitor/ while that server is running.

The camera-monitor subfolder contains the viewer, 18 original snapshots, two annotated snapshots, source-metadata.json and state.json. The state file records retrieval times, source Last-Modified headers, publication ages, per-frame SHA256 hashes, duplicates, model boxes, SAM usage, errors and the final report. Last-Modified is publication time, not guaranteed camera exposure time. The viewer supports per-inspection boxes and a clearly labeled 10-times-speed snapshot replay.

The delivered ZIP and FILE_MANIFEST.json include these files. The worker and all paid calls have stopped. The viewer and existing recording server are read-only. The test did not add continuous surveillance to the core evaluation API.

## Limits and next steps

The observed public feed refresh rate was too slow for continuous monitoring. Repeated frames are source freshness evidence, not evidence that the scene was unchanged. The small sample provides no verified incident, speed, identity, tracking or accuracy conclusions. Detection totals are not counts of unique vehicles. Human labels and a source with an appropriate refresh rate are required for a scored monitoring evaluation.

Browser checks confirmed exact-frame inspection selection, snapshot replay and no reported JavaScript errors. The final repository gate uses mock mode. No claim of production readiness follows from this camera demonstration.

## Sources

- City dataset and camera listing: https://data.austintexas.gov/Transportation-and-Mobility/Traffic-Cameras/b4k4-adkb
- Camera metadata endpoint: https://data.austintexas.gov/resource/b4k4-adkb.json?camera_id=2
- Official image service description: https://github.com/cityofaustin/atd-data-tech/issues/7676
- Image endpoint: https://cctv.austinmobility.io/image/2.jpg
- City source terms: https://data.austintexas.gov/stories/s/ranj-cccq

The official dataset metadata lists PUBLIC_DOMAIN. This describes the dataset metadata license field; consult the linked city terms for image use. Downloaded content was treated only as data.
