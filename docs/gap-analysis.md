# What this is, and what is still missing

## In plain words

You can point a vision model at a photo and ask it to outline "the red safety tag". Sometimes it
misses the tag, or outlines something else. BLINDSPOT CI finds out how often and under which
conditions, before anyone relies on it.

It does four things:
1. Takes photos that a person has labeled (a person drew a box around the object, or confirmed it is absent).
2. Lets an AI agent (Muse Spark) choose which photo to test next, so it hunts for weak spots instead of testing at random.
3. Asks the model under test (SAM 3.1) to outline the object, then scores the result with plain Python against the person's box. No model grades itself.
4. Writes a report: pass counts with uncertainty, every failure with its photo, and an evaluation card.

It is an evaluation tool for a vision model. It is not the vision model, and it is not a safety approval.

## Is this the end goal?

The goal is a hackathon project: an agent that finds blind spots in SAM 3.1, backed
by real, human-labeled evidence. The software for that is built and works. The evidence is the weak part.

- Real data in use (never generated): 24 Open Images photos, 21 harder Open Images photos, and 112 frames
  from 14 DAVIS video clips. People drew all the labels. DAVIS also has a person-drawn mask per frame.
- Not evidence: the 5 drawings used for the free demo, and any Muse Image variants. They are labeled as such
  and are kept out of every result.
- Missing: photos of your actual tray tag. Everything so far is proxy data (hydrants, stop signs, animals).
  If your real use is the tray tag, that data is the single biggest gap, and no tooling replaces it.
- Live API access is intermittent (it failed again on 2026-11-01). The 132-case COCO set was run live once it returned (`docs/results-coco.md`).

## What serious teams and standards ask for, against what exists

Sources are listed at the end. Most were read as search summaries, not full texts. Treat the mapping as a
guide and check the standards themselves before quoting them.

| What is asked | Where it comes from | Status here | What closes it |
| --- | --- | --- | --- |
| Test sets that represent real use, with their makeup documented | EU AI Act Article 10 as summarized by compliance vendors | Partial. Sets are documented, but none comes from the tray scene | Label 100 or more tray photos across the conditions you care about |
| Results sliced by condition, with uncertainty | ML Test Score model tests; slice-discovery work | Done. Wilson intervals, underpowered flags | None |
| Enough cases to back a claim | Statistics; SOTIF notes that rare events need large samples | Stated, not met. Claiming under 1% failure needs 299 failure-free independent cases per slice | Collect more scenes, then report counts per slice |
| Independent labels and a human performance bound | SAM 3 SA-Co Gold uses triple annotation | Missing. One annotator for most labels | Second annotator on at least 30 percent of cases. `compare-labels` now reports agreement and kappa |
| Mask quality, not only box overlap | Segmentation benchmarks score masks | Done for the video set: mean J 0.93, boats weakest at 0.79 (see `docs/results-hard-and-video.md`). Not possible for Open Images, which has boxes only | Label masks for your tray photos if outline quality matters |
| Coverage of the conditions that trigger failures | ISO 21448 (SOTIF) triggering conditions | Partial. Conditions are measured but no coverage matrix | List the conditions your tray faces and count cases per cell |
| Data and pipeline checks, reproducible runs | ML Test Score data and infrastructure tests | Mostly done. Image hashes, run ids, replayable cache, CI file | Run the CI once on a real repository |
| A regression gate between model versions | ML Test Score model tests | Done. `compare-runs` pairs scored cases and uses a two-sided exact sign test | Keep baseline and candidate runs on the same cases, then inspect the regression and fix lists |
| Monitoring after deployment | ML Test Score monitoring tests | Missing, and out of scope until something is deployed | Log live inputs and re-test on a schedule |
| Human review of discovered failure slices | Johnson et al. found that a coherent slice does not mean people can explain it | Done by design. The report shows each failure with its photo for a person to judge | None |
| Security, privacy, spend limits | OWASP guidance for LLM agents; the security review done here | Done for local use. No sign-in, so public use must stay mock-only | Add sign-in before any public live deployment |

Google's ML Test Score takes the minimum across four sections (data, model, infrastructure, monitoring),
so the weakest section sets the grade. Here monitoring is the weakest.

## Data reality, in numbers

| Set | Real? | Size | Honest sample size |
| --- | --- | --- | --- |
| Open Images, fire hydrant and stop sign | Yes | 24 photos, 22 scored | 22 |
| Harder Open Images | Yes | 21 photos | 21, and only 1 hard negative |
| DAVIS video frames | Yes | 112 frames | about 14 clips |
| COCO val2017 | Yes | 132 photos | 10 to 30 per condition |
| Corruptions of real photos | Measured, not generated | 22 tests from 5 photos | 5 |
| Free demo drawings | No, drawings | 5 | not evidence |

That is small. A team deciding whether to rely on a model would expect hundreds of photos per condition they
care about, drawn from the real setting, with two annotators.

## Order of work from here

1. You: photograph the tray tag in the real conditions, label with `python -m blindspot_ci.cli label`, and ask a second person to label a third of them.
2. Rerun `experiment` live on the tray photos once they exist.
3. Run `python -m blindspot_ci.cli compare-labels first.json second.json` and fix labels where people disagree.
4. Run `scripts/eval_masks.py` for mask scores on the video set.
5. Run `compare-runs` on paired baseline and candidate results, then build the coverage matrix once real tray results exist.

## Sources

- Nielsen, Salib, Sculley. The ML Test Score. https://research.google/pubs/pub46555/
- Johnson et al. Where Does My Model Underperform? A Human Evaluation of Slice Discovery Algorithms. https://arxiv.org/pdf/2306.08167
- Eyuboglu et al. Domino, as described at https://hazyresearch.stanford.edu/blog/2022-04-02-domino
- SAM 3: Segment Anything with Concepts. https://arxiv.org/html/2511.16719v1 (benchmark figures differ between secondary summaries, so verify against the paper)
- EU AI Act Article 10 as summarized by https://presencis.com/regulations/eu-ai-act/conformity/article-10-data-governance (a vendor page, not the legal text; paragraph numbering and dates are unverified)
- ISO 21448 (SOTIF) as summarized at https://arxiv.org/pdf/2302.00437 and https://arxiv.org/pdf/2404.06288 (no sample-size formula was found)
- Hanley and Lippman-Hand 1983, the rule of three, used in `blindspot_ci/experiment/power.py`
- Earlier references, with their own depth notes, are in `docs/research-and-standards.md`
