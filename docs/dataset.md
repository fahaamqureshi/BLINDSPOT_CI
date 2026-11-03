# Building the real evidence set

For new installations, use the [workspace workflow](DEVELOPER_GUIDE.md) so imports stay outside the installed package. Pass the same --workspace path to label, import-photos and serve. Relative image_source paths resolve against the labels file. The checkout-based examples below remain available for existing users.

The fixture drawings only prove the code works. A judge learns something about SAM 3.1 only from
real photos that a person labeled. There are two ways to get them: public open data (below) or your
own photos (the rest of this page). The two sets stay separate (`open` and `real`) and are never
mixed in one result.

## Open data: Open Images V7

`scripts/fetch_open_data.py` builds a real, human-labeled set with no photography. The set holds
everyday red coloured objects: fire hydrants and stop signs. Boxes were drawn or verified by Open Images annotators,
never by SAM or Muse. Absent cases are images where annotators verified the class is not there.
Every image keeps its own CC BY license, author and landing page in `label_provenance`.

```powershell
python -I scripts/fetch_open_data.py
python -m blindspot_ci.cli import-photos "$env:TEMP\blindspot_openimages\open-labels.json" --dataset open
.\scripts\live_experiment.ps1 -Dataset open -Steps 8
```

The first command downloads about 200 MB of public CSV files once, then each chosen photo. It checks
every photo against Open Images' MD5 and skips images with EXIF rotation, because their boxes could
be misaligned. Conditions are measured, not guessed: `low_light` (mean luminance under 70 of 255),
`occlusion` and `truncated` (annotator flags), `small_object` (box under 3 percent of the image),
`normal`, and `absent`. The photos and the manifest stay out of git and out of the ZIP, and the
script rebuilds them.

Limits: the objects are not a maintenance tray tag, so the result says how SAM 3.1 handles everyday red
objects in public photos, not how it handles your tag. Open Images boxes are not perfect, and a class
can be present but unlabeled outside the verified negatives. Quote counts, not percentages.

## Your own photos

## What to photograph

The planned use case, not yet tested: a red safety tag on a maintenance tray. Take 20 to 40 photos of your own tray and tag. Aim
for a mix, so the test order has something to choose between:

| condition | how many | what the label says |
| --- | --- | --- |
| `normal` | 4 to 6 | tag clearly visible, draw the box |
| `low_light` | 4 to 8 | lights off or one lamp, tag still visible, draw the box |
| `angle` | 4 to 8 | steep or odd angle, tag visible, draw the box |
| `occlusion` | 4 to 6 | a hand, tool or cloth covers part of the tag, draw the box on what you see |
| `absent` | 4 to 6 | same tray, no tag at all |
| `unknown` | 0 to 3 | you truly cannot tell, so it is not scored |

A recovery view is a second photo you took on purpose. Point a failing case at it with
`recovery_case`. The app never claims a camera moved.

Rules: use only photos you own, with no faces, names or other private details. Photos are sent to
Meta's API in Standard mode.

## How to label

Fastest way: the local labeling tool. Put your tray photos in one folder, then run

```powershell
python -m blindspot_ci.cli label --folder "C:\Users\YourName\Pictures\tray_photos" --annotator "Your Name" --out my-labels.json
```

Open http://127.0.0.1:8001, drag a box around the tag on each photo, pick the condition, and press
Save and next. Choose "object absent" for photos with no tag and "cannot tell" for unclear ones. The
tool shows photos upright, so the numbers match what the importer checks, and it stores your name on
every label. Then run `python -m blindspot_ci.cli import-photos my-labels.json`. The steps below do the
same thing by hand.

1. Open the photo upright, the way a person sees it.
2. Write the box as pixel numbers `[x1, y1, x2, y2]`: left, top, right, bottom. Any image viewer that
   shows the cursor position works. Windows Paint shows it in the status bar.
3. Draw the box around the tag only. Use `visible`, `absent` or `unknown` for the visibility.
4. Label before you ever run the model. Never copy a box from SAM or Muse. That would be the model
   grading itself.
5. If you can, ask a second person to label some of the same photos on their own, without seeing
   your boxes first. Put their name as annotator in their own file and as `reviewer` in yours where
   they checked a label. A name in `reviewer` alone does not give the release gate an agreement
   score. To get that score, save the two files and compare them as below.

## Import

Copy `datasets/real-labels-template.json`, add one entry per photo, then run:

```powershell
python -m blindspot_ci.cli import-photos my-labels.json
```

The importer applies the phone's rotation flag, shrinks photos to at most 1600 pixels on the long
side (boxes scale with them), checks every box, and records a SHA-256 hash of each stored image. The
loader refuses a photo that changed after labeling. Results go to `datasets/real/` and
`datasets/real_manifest.json`. Both are git-ignored and never added to the submission ZIP.

Replace every placeholder value in the template copy before you import, including the example
photo path, the annotator name and the box. The importer stops on the first photo it cannot find.

For second annotator coverage, keep the first and second label files and run the compare command.
The JSON it prints is the agreement file the release gate reads.

```powershell
python -m blindspot_ci.cli compare-labels my-labels.json second-labels.json
```

## Run it

```powershell
.\scripts\live_experiment.ps1 -Dataset real -Steps 8
```

Or set `BLINDSPOT_PROVIDER=meta`, `LIVE_API_ENABLED=true` and `BLINDSPOT_DATASET=real`, then use
`python -m blindspot_ci.cli serve` and press Run.

## How to read a result

- `PASS` means the best box overlapped your label by at least the threshold (IoU 0.35 by default). It
  is one example, not a safety approval.
- `FAIL_FALSE_NEGATIVE`: you labeled the tag visible and SAM found nothing.
- `FAIL_FALSE_POSITIVE`: you labeled it absent and SAM found something.
- `FAIL_LOCALIZATION`: SAM found something, but not where you drew the box.
- `UNKNOWN`: not scored. `ERROR`: the call or parser failed. Neither counts as a model miss.
- With 20 to 40 photos the numbers are rough. Report counts such as "3 of 8 low-light photos failed",
  not percentages that sound precise.
