# Blindspot CI in simple words

Blindspot CI is a release gate for vision models. A vision model looks at a
photo or a video and tries to find things in it. This tool checks whether the
model finds those things well enough, in the kinds of photos that must work,
before a team ships it. It tells a quality engineer three things: should this
go out yet, why not, and what to fix first.

Quality means checking work before users get it. The CI part means the check
can sit in the automatic tests that run on every code change, because the gate
answers with an exit code that a build pipeline can act on.

This is not a new vision model. No model here was trained or fine tuned by
this project. The project uses Meta models through an API, which means it
sends a request and gets an answer back. The model under test is SAM 3.1, and
the helper models are Muse Spark, Muse Image, Muse Voice Transcribe, and
Muse Wonder. Plain Python code, not a model, works out every score.

## The driving test idea

Think of a driving test for a new driver.

- The learner is the vision model. It has to show what it can do.
- The test routes are the photos and videos. Some are easy, in bright light.
  Some are hard, in low light, with small objects, or with the object half
  hidden.
- The examiner answer sheet is the set of labels drawn by a person before the
  test. The person marks where the object is, or marks that nothing is there.
- The marking is done by plain Python. It compares the model box with the
  person box and measures how much they overlap.
- The test result is the gate verdict. It can say ready, not ready, or not
  enough solid evidence yet. A person still makes the final call.

A driver can look fine on one sunny road and still fail at night. A vision
model can look fine in one bright demo photo and still miss small or dark
objects. One good demo proves very little. A fair test checks the hard cases
on purpose, with the answers hidden until marking time.

## How it works in five steps

1. A person labels the test cases first. The person draws a box around the
   object, or confirms that the object is not there. These labels are the
   answer sheet, and they stay hidden from the model and from whoever picks
   the test order.
2. A test order is chosen. A script can work through the list, or the Muse
   Spark planner can pick the next case. The planner never sees the labels.
3. SAM 3.1 tries each case. It returns a box and an outline for what it
   thinks it found. Each live call costs about a quarter of a cent, and every
   run has a call limit and a spend cap that stop it early.
4. Plain Python marks the work. For one photo, the model box must overlap the
   person box enough to pass. The overlap bar for one photo is 0.35. Then the
   marks are grouped by kind of photo, such as normal, low light, or small
   object.
5. The Release Gate gives the verdict and the fix list. For a kind of photo
   that must work, the group bar is 9 of 10, which is a 90 percent pass rate.
   The gate prints one line per check, the kinds that failed, and what to try
   next. The full run is saved, so anyone can read it again for free with no
   new model calls.

## Who does what

| Name | Job in plain words | Honest note |
| --- | --- | --- |
| Muse Spark 1.3, the investigator | Picks which test to run next, using function calling, and says why | Built and working, but the saved headline runs used a scripted test order instead. Call this agent assisted, not fully on its own. |
| SAM 3.1, the eyes | Looks at each photo or video and returns boxes and outlines | This is the model being tested. It does not mark its own work. |
| Plain Python, the examiner | Compares each model box with the person box and works out every score | Python alone produces scores. Nothing else can change a score. |
| Muse Image 1.0, the stress helper | Makes harder copies of a photo, such as low light, glare, or blur versions | The box is copied from the source photo and a person must confirm it still fits. Its output never changes a score. |
| Muse Voice Transcribe 1.0, the note taker | Turns a spoken reviewer note into text | It only writes notes. It never changes a score. |
| Muse Wonder 1.0, the plain words helper | Writes a short plain language audit of a finished run | A person reads it next to the scores, because it can be wrong. It never changes a score. |
| A person | Draws the labels, reads the failures, and makes the ship or no ship call | The gate is advice with evidence. It is not a safety approval. |

Function calling means the planner asks for the next step by naming a known
tool and a case that has not been tested yet. If it asks for anything else,
the run stops safely and nothing is guessed.

## What the screen shows

The result page starts with the verdict in big plain words, then the reason,
then a table by kind of photo, then each failed photo with the person box and
the model box drawn on it, then a what to fix first list. A badge shows
whether the answers were live model calls or scripted practice answers, so a
practice result cannot be mistaken for a real one.

There are four verdicts. These are the real meanings used by the gate today.

| Verdict | Exit code | Plain meaning |
| --- | --- | --- |
| GO_CANDIDATE | 0 | Every check passed. A person still decides. This has never been reached yet. |
| NO_GO | 1 | A kind of photo that must work is below the bar. In plain words: do not ship yet. |
| NEEDS_REVIEW | 2 | Nothing clearly failed, but the evidence is thin, unchecked, or may not be a fair test. |
| DEMO_ONLY | 3 | The answers came from a script or from made up images. This is practice only and proves nothing about the model. |

Exit code 4 means a file could not be read. Scripted, made up, or damaged
evidence can only ever get DEMO_ONLY, however good the numbers look.

## Real results so far

These results are real. SAM 3.1 gave the answers, a person gave the labels,
and plain Python worked out the scores. No model graded anything. Full
details, run ids, and free commands to read the saved runs again are in
`docs/real-results.md` and in the README.

### Photos: NO_GO

- Set: 132 COCO photos of fire hydrants, stop signs, and traffic lights. Run
  id `a165cd6773cd433a`, live calls.
- Verdict: NO_GO, which means do not ship yet.
- Why: in low light the model found 6 of 10 objects, and for small objects it
  found 19 of 24. The group bar is 9 of 10. Both kinds fell below the bar.
- In plain words: the model did well in easy photos and missed too much when
  the light was low or the object was small. That is the blind spot this tool
  exists to find.

### Video frames: NEEDS_REVIEW

- Set: 112 frames taken from 14 DAVIS video clips. Run
  id `8f6003378706480a`, live calls.
- Verdict: NEEDS_REVIEW, which means the evidence is not solid enough yet.
- Why: frames from one clip look a lot like each other, so 112 frames act
  more like 14 separate tests. There is also a worry that SAM may have seen
  DAVIS while it was being trained, which would make the test too easy. That
  worry is marked UNVERIFIED in the project notes and should be checked
  against the SAM papers before anyone quotes it.
- In plain words: good marks on a test the student may have seen before do
  not prove very much, so the gate asks for a fairer test.

### Long video: NO_GO

- Set: one public crowd video called MOT20-03, with 2,405 frames and 16
  people followed from boxes drawn by a person. Corrected run
  id `e30e0efcc7ca43a7`.
- Verdict: NO_GO.
- Why: only 3 of 16 people were followed correctly on at least 90 percent of
  their scored frames. The person in the middle was followed on 82.5 percent
  of frames. Most misses were a box that came back in slightly the wrong
  place, not a person who vanished.
- One more honest detail: the answer stream stopped early, at frame 2351 of
  2405. The last 108 labeled frames count as errors in the score, because the
  answer never arrived for them.
- The first scoring of this same video wrongly showed 0 of 16, because the
  service sent the boxes back at a smaller size and the marking compared the
  wrong sizes. The team found the bug, fixed it, and marked the saved answer
  again for free. One paid call covered the whole test.

The long video test used one paid call, priced at 0.481 US dollars in the run
plan, under a 4.00 US dollar cap set for that test. Reading any saved run
again costs nothing and makes no model calls. The price is a plan price from
the dry run, not a provider bill, and the project notes say so.

The code behind this is checked hard. There are 273 automated tests. The
project gate is `python scripts/check.py`, and it prints Summary: PASS when
the code checks, the tests, the document style checks, and the secret checks
all pass. GitHub runs the same tests on Python 3.11 and Python 3.13 on every
push, and CI is green on main. CI means the automatic checks that run whenever
code changes.

## Two made up stories, not results

The two stories below help picture where this tool would be used. They are
made up use cases. They are not measurements, not customers, and not proof
that the model works in these places. No pass counts are given for them here,
so that no made up number can be mistaken for a real result.

### Made up story 1: the factory safety tag

Picture a factory where a worker checks a machine before fixing it. A red
safety tag on a maintenance tray shows that the machine is locked and safe to
touch. A camera model that misses the tag in poor light could send the wrong
signal at the worst moment.

This was the first planned use for Blindspot CI. It has not been tested yet,
because no photos of the tag on the tray exist yet. If the team takes those
photos and a person labels them, the screen would group the marks by kind of
photo and point at the weakest kind first. A made up screen would read like
this, in words only:

```text
Made up screen. Not a measurement.
Verdict: do not ship yet.
Why: misses rise when the tray is in shadow.
Fix first: take and label more shadow photos, then test again.
```

Until real tray photos exist, this story is only a picture of the idea. The
measured results in this document come from the public photo and video sets
above, not from a factory.

### Made up story 2: the warehouse shelves

Picture a large warehouse of the kind people picture when they think of
Amazon, with tall shelves, dim aisles, and boxes that half hide each other. A
camera model might read shelf labels well in a bright aisle and miss them at
the back of a dark one, or mix up two boxes that look alike.

In that made up case, the value of the tool would be the grouped report: not
one big score, but a short list that says which shelf condition fails, with
the failed photos shown one by one so a person can judge. Amazon has not used
this tool and is not a customer. This story only shows the shape of the
problem the tool is built for.

A made up buyer story goes with these. Imagine a lead engineer at a small
camera company on the Friday before a release. The demo looked great on
Monday. She runs the gate, gets NO_GO for low light, fixes the weakest cases
first, and ships a week later with evidence instead of hope. That buyer is
imagined. The next section says who we think the real buyer is, and how sure
we are.

## Who might buy this

Our best guess at the buyer is the computer vision or quality engineer who
has to sign off on a vision model before it ships, and the lead who trusts
that sign off. Their problem is simple to state: a model update can look
better in a demo and quietly get worse on dark, small, or half hidden
objects. Checking a few photos by hand misses that. Repeating the same fair
test on every release, with the same hidden labels and the same gate, catches
it before users do.

This buyer is a hypothesis. No customer has been verified, no one has paid,
and no sales claim is made here. What exists today is the working tool, the
real measured runs above, and a clear next buyer to go and test the idea
with.

## Why not just ask a chat model

A chat model such as ChatGPT can look at a photo you show it and talk about
what it sees. That is useful, and it is a different job from this one.

- A chat answer is words about the photos in front of it. Blindspot CI gives
  counts over a whole labeled set, worked out the same way every time, so two
  model versions can be compared fairly.
- In a chat, a model can end up judging its own kind of answer. Here the
  labels come from a person, stay hidden during the test, and plain Python
  does the marking. No model grades itself.
- A chat does not protect you from weak evidence. The gate refuses to treat
  scripted answers, made up images, or a test the model may have already seen
  as proof. The strongest verdict also needs fresh photos the model cannot
  have seen, plus labels from a second person.
- A chat leaves no gate for a build pipeline. This tool saves every run with
  its run id and image fingerprints, reads it back for free, and answers with
  an exit code, so a release can be stopped by a rule instead of an opinion.

In short: ask a chat model to explain a photo. Use Blindspot CI to decide,
with evidence, whether a vision model is ready to ship.

## What is built and what is not built yet

| Part | State | Plain meaning |
| --- | --- | --- |
| Test harness and Release Gate with four verdicts and exit codes | Built and tested | The main tool works end to end on saved runs with no spend. |
| Python scoring against person labels, with labels hidden while testing | Built and tested | Scores come from code and person labels only. |
| Result screen, how it works page, and evaluation card | Built and tested | A judge or engineer can read a verdict, the failed photos, and the fix list. |
| Muse Spark planner that picks tests by function calling | Built, with a limit | It works, but the saved COCO and DAVIS runs used a scripted test order. This is agent assisted, not fully on its own. |
| Harder photo copies, spoken notes, and the plain words audit | Built, as helpers | They help people test and review. None of them can change a score. |
| Three real measured runs on photos and video | Done | COCO photos NO_GO, DAVIS frames NEEDS_REVIEW, and the long crowd video NO_GO. |
| 273 automated tests, the `scripts/check.py` gate, and GitHub checks on Python 3.11 and 3.13 | Done and green | The gate prints Summary: PASS and CI is green on main. |
| Free public demo guide for Northflank in `docs/free-deployment.md` | Written down, owner step left | The guide deploys only the scripted mock demo with no key. The owner still has to connect the account, so this is documented and ready to follow, not a hosted live service. |
| Own photos taken after the model release, such as the factory tray tag | Not done yet | No such photos exist yet. The planned tray tag case has no photos at all. |
| A second person labeling the same cases | Not done yet | Most labels come from one person, so label mistakes are harder to catch. |
| A GO_CANDIDATE verdict | Never reached | The gate has never said every check passed. Fresh own photos and a second labeler are needed first. |
| Long videos MOT20-02 and MOT20-05 | Not run | Their uploads, at 76 and 86 MB, hung, so only MOT20-03 was tested. |
| More than one long video, and verified paying customers | Not done yet | One crowd video and 16 people is a start, not a broad claim. There are no verified customers. |

## Honest limits

- This is a test harness with a careful gate. It is not a benchmark, not a
  ranking of models, and not a safety approval. A person decides every
  release.
- The samples are small. The photo result rests on 10 to 30 cases per kind,
  the video frames act more like 14 clips, and the long video follows 16
  people in one sequence. Treat the numbers as warning signs with evidence,
  not as exact failure rates for the real world.
- Most labels come from one person. If that person drew a box slightly
  wrong, the score inherits the mistake. A second labeler is the fix, and it
  is still missing.
- The model may have seen some test sets while it was being trained. That
  overlap is unverified for DAVIS and unknown for the photo sets. It is one
  reason the strongest verdict needs fresh photos taken after the model
  release, and those photos do not exist yet.
- Frames from one clip or one tracked person look alike, so counting every
  frame as separate proof overstates how sure we can be. The reports say this
  where it matters.
- The long video score includes 108 frames whose answers never arrived
  because the stream stopped early. They count as errors, which makes that
  one score a little harsh, and the notes say so plainly.
- Practice answers prove only that the code runs. Scripted, made up, and
  generated evidence can only ever get DEMO_ONLY.

## The 30 second pitch

Read this out loud. It takes about 30 seconds.

Blindspot CI is a driving test for vision models. A person labels the photos
first, SAM 3.1 tries to find each object, and plain Python marks the answers,
so no model grades itself. On real photos the gate said do not ship yet,
because low light found only 6 of 10 objects. On a long crowd video it
followed only 3 of 16 people well. It is a release gate for engineers, with
273 automated tests behind it, not a new model.

## Where to check every number

- The README gives the headline results, the four verdicts, and free commands
  to read the saved photo and frame runs again.
- `docs/real-results.md` gives the three real results, run ids, caveats, and
  the rebuild check for the long video.
- `docs/long-video-test.md` gives the long video method, the 4.00 US dollar
  cap used for that test, and the smaller box fix.
- `docs/release-gate.md` gives the verdict rules, checks, and exit codes.
- `docs/free-deployment.md` gives the free Northflank demo steps and the
  owner actions they still need.
- `scripts/check.py` is the project gate. It passes only when the code checks,
  all 273 tests, the document style checks, and the secret checks pass.
