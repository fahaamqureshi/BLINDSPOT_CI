# MOT20 long video test

This pipeline uses the MOT20 training sequences MOT20-02, MOT20-03 and MOT20-05. The labels are
human annotations. Target tracks are selected from label rows only.

Run the range-only preflight:

    python scripts/fetch_mot20.py --preflight

The default output is a fresh directory under the system temporary directory. Use `--out DIR` to
choose another output directory and `--max-bytes N` to cap bytes fetched from each remote file. The
5 GB image archive is sampled with HTTP range requests and is never downloaded in full. The labels
archive is about 13.9 MB and is saved in the output directory.

Build the manifest after preflight:

    python -m blindspot_ci.experiment.mot_importer --labels DIR/MOT20Labels.zip --preflight DIR/mot20-preflight.json --out DIR/mot20-manifest.json

Each selected track has at least 300 labeled frames. Selection is deterministic and spreads tracks
over box-size and visibility quartiles. The seed is the first visible, fully in-frame box. Rows after
the seed with no label are marked `NOT_SCORED`.

Condition tags are measured from labels and sampled luminance. They include `occluded`,
`small_object`, `truncated`, `dark` and `normal`. If image ranges cannot be read, dark is recorded as
`dark:UNVERIFIED`. The manifest keeps the source URL, frame metadata, label archive SHA256 and
license text.

MOT20 is published under the Creative Commons Attribution-NonCommercial-ShareAlike 3.0 License
(CC BY-NC-SA 3.0). It is non-commercial data and must not be redistributed. The output directory
must remain outside `datasets/` and downloaded data must not be committed.

The source descriptions include crowded indoor stations and night scenes from elevated viewpoints.
They are not evidence that one fixed monitoring camera follows a target, so the research use case
must state that limitation.

## Run the offline plan

The command below reads only the manifest and prints one call per sequence, its frame count and its
cost. It makes no network call.

    python -m blindspot_ci.cli long-video --manifest DIR/mot20-manifest.json --sequences MOT20-03 MOT20-02 MOT20-05 --budget-usd 4.00 --dry-run

For a live owner-run test, set `BLINDSPOT_PROVIDER=meta`, `LIVE_API_ENABLED=true` and `MODEL_API_KEY`
in the local environment. The command seeds up to 16 human boxes in one forward tracking call per
sequence. A shared budget is reserved before each call. There are no retries. A missing setting stops
the command before network use. Raw streamed text is saved under `artifacts/video-raw` before parsing.

    python -m blindspot_ci.cli long-video --manifest DIR/mot20-manifest.json --sequences MOT20-03 --budget-usd 4.00 --min-iou 0.35

The normal run report is saved under `artifacts/runs`. Full frame results are in the matching
`.temporal.json` file. Read them without network access:

    python -m blindspot_ci.cli temporal-report --run RUN_ID

To replay a saved raw stream without a key, live flags or network access, keep the manifest for its
human labels and name one sequence. `PATH` may be the raw text file or a directory containing the
matching `<run id>-<sequence>.txt` file.

    python -m blindspot_ci.cli long-video --manifest DIR/mot20-manifest.json --sequences MOT20-03 --from-raw PATH

The temporal report describes misses, recovery, ten time-bin dropout, condition retention, and the
luminance range. Frames from one track are strongly correlated, so intervals from this report
overstate certainty. Dark is relative to each sequence and means little when its luminance range is
narrow. Use `fixtures/policies/long-video.json` with `release-gate --policy`; it uses the MOT20
conditions and leaves the default numeric thresholds unchanged.

MOT20 human boxes cover the whole person including hidden parts, while SAM boxes cover what it sees.
Low scores on frames tagged occluded may reflect that labelling convention and not a model loss.
MOT20 is not a fixed-camera dataset.

The provider accepts a video URL directly. If the URL is refused, a future fallback could upload the
file and use its returned file ID. That is a reasonable compatibility improvement, but it is not part
of this offline wiring.
