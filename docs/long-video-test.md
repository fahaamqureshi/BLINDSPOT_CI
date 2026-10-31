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
