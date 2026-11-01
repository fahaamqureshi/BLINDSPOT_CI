# Results: SAM 3.1 on Open Images everyday red coloured objects

Run on 2026-10-31 through the Meta Model API (Standard mode). Every number below comes from a saved
report in `artifacts/runs/`. Python scored every case. Nobody graded by eye, and no model graded.

## Set up

- Photos: 24 from Open Images V7 (validation and test splits), CC BY 2.0, each with its own author and
  landing page recorded in the manifest. Built by `scripts/fetch_open_data.py` with seed 7.
- Task: segment a fire hydrant or a stop sign. The prompt is the class name.
- Labels: boxes drawn or verified by Open Images annotators. Absent cases are images where annotators
  verified the class is not there. No label came from SAM or Muse.
- Pass: best box overlap (IoU) of at least 0.35, or no detection on an absent photo.
- Agent: Muse Spark 1.3 picked each test by function calling. SAM 3.1 segmented. Run 6459e3b33ccf427e.

## Main result

After adjudication: 20 of 22 scored cases passed (95 percent Wilson interval 72% to 98%), with 2 cases
marked unknown. Run cdd877484c9f4fac covers all 24 cases. SAM answers were replayed from the cache of
the first run (6459e3b33ccf427e), so no new SAM call was made.

Before adjudication the same photos scored 20 of 24 (64% to 93%). Both numbers are kept here on
purpose. The two removed cases were doubtful labels, not model passes, and the first run is saved
unchanged.

Adjudication record: on 2026-10-31 the project owner told the assistant to mark `oi_normal_03` and
`oi_low_light_04` unknown. The assistant had looked at both photos. There was no second annotator, so
this is one person's call and not an independent review. The original labels, the reason and the
decision are stored in each case's `label_provenance.adjudication`.

| Slice | Passed of scored | 95% interval | Note |
| --- | --- | --- | --- |
| normal | 5 of 5 | 57% to 100% | 1 case marked unknown |
| low light | 3 of 3 | 44% to 100% | underpowered, 1 case marked unknown |
| truncated (object cut by the edge) | 4 of 4 | 51% to 100% | underpowered |
| occlusion | 2 of 2 | 34% to 100% | underpowered |
| small object | 2 of 2 | 34% to 100% | underpowered |
| absent (false alarms) | 4 of 6 | 30% to 90% | the only real failures |

Where it passed, the best box overlap was high, from 0.79 to 0.998. The mask followed the object
outline on a real photo in the browser (normal case 1, IoU 0.988).

## The four failures, looked at one by one

| Case | What the photo shows | What it means |
| --- | --- | --- |
| absent 01 | A "NEW ROAD LAYOUT AHEAD" road sign | A real false positive: SAM boxed a road sign as a stop sign |
| absent 02 | A metal object that looks like a teapot sculpture | A real false positive: SAM boxed it as a fire hydrant |
| low light 04 | A pink and blue pipe assembly labeled fire hydrant | Doubtful label. The photo is not dark, only the grass is, so the condition tag is also weak |
| normal 03 | A red street fire-alarm call box labeled fire hydrant | Probably a label error. SAM finding no hydrant may be right |

The last two were marked unknown with `python -m blindspot_ci.cli adjudicate` (see the record above).
That leaves the two false positives as the only model failures in the scored set.

What the failures suggest, as hypotheses and not findings: SAM 3.1 is strong when a real object is
there, and weaker at saying no on look-alikes (a road sign, a metal object). Six absent photos cannot
confirm that.

## Stress tests

- Measured corruptions (run c85d2c55664044c2): 5 passing normal photos, each degraded by low light,
  blur, JPEG and contrast at severities 3 and 5. Muse chose to stop after 22 of the 40 variants. All 22
  passed, including severity 5. This means no failure was found in the 22 tested, not that the other 18
  would pass. The interval for 22 of 22 is roughly 85% to 100%.
- Muse Image variants: only run on the synthetic drawings, where SAM found nothing. Not evidence.

## Did the agent beat random order?

No evidence it did. On a run of 8 tests (run f48fd1b4e15f442c) the agent found 1 of the 4 failures,
where a random order is expected to find 1.33. Its first failure came at test 7, where random order
expects 5. The chance of a random order doing as well is 0.83. With 24 cases this cannot separate
skill from luck either way. The value of the tool today is the evidence pipeline: labeled data, scoring,
intervals, the card and the audit.

## Limits

- This is public photos of hydrants and stop signs, not a maintenance tray tag.
- Counts are small. Quote counts with their interval, never a bare percentage.
- Open Images labels are not perfect. Two of 24 were found doubtful and adjudicated by one person. The
  other 22 have not been reviewed a second time (0 of 24 have a named independent reviewer).
- Condition tags are measured by rule (mean brightness, annotator flags, box size) and fixed before
  the run. They were not tuned after seeing results, so low light 04 stays as tagged.
- Results hold for sam-3.1 through the Meta Model API on this date.
- A pass is not a safety approval.

## Reproduce

```powershell
python -I scripts/fetch_open_data.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_openimages\open-labels.json" --dataset open
$env:BLINDSPOT_MAX_CALLS = "60"
.\scripts\live_experiment.ps1 -Dataset open -Steps 24
python -m blindspot_ci.cli card --run <run id>
```

Cost: the six saved run reports sum to $0.32, plus a few cents for audits. About $0.35 in total.
