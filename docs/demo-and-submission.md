# Demo and submission

## 90-second demo script

Use the saved runs. They are free and show real results. Start the app with `python -m blindspot_ci.cli serve`.
Never show a `MOCK_FIXTURE` number as a SAM result.

1. The problem (10 seconds). Say: "A vision model can look great in a demo and still fail on dark, small or half
   hidden objects. BLINDSPOT CI tests it against human labels and tells a QA engineer whether it is ready to ship."
2. The verdict (25 seconds). Open `/app?run=a165cd6773cd433a&dataset=coco`, the saved live COCO run. Read the
   verdict, NO_GO (Do not ship yet), then the sentence under it, then the failing rows: low light found 6 of 10
   and small objects 19 of 24, against a bar of 9 of 10.
3. What to fix (10 seconds). In the Release gate panel, read the what to fix list, such as fixing the failing
   low light and small object cases and re-running on fresh photos.
4. The real long video test (20 seconds). Say: "We followed 16 people through a public 2,405 frame crowd video
   with one paid call. Only 3 of 16 were followed on at least 90 percent of their frames, so the gate says NO_GO.
   Our first scoring wrongly showed 0 of 16 because the service shrank the video and returned boxes at the
   smaller size. We caught it, fixed it, and re-scored the saved answer for free."
5. Honest limits (15 seconds). Say: "Most labels come from one person, the sets are small, the saved COCO and DAVIS
   runs used a scripted test order, and this is not a safety approval."
6. What comes next (10 seconds). Say: "Next are our own photos taken after the model release, and a second
   labeler. Until then the gate cannot return GO_CANDIDATE."

## Submission checklist

Items marked UNVERIFIED have not been checked against the official Rules. The event page is
https://cerebralvalley.ai/e/meta-ai-developer-hackathon and lists a deadline of Nov 4 2026, 9:00 PM ET.

- [ ] Read the official Rules. Required fields, eligibility and track (Indie or Startup, undecided) are UNVERIFIED.
- [ ] Video length limit: UNVERIFIED.
- [ ] Repository and write-up requirements: UNVERIFIED.
- [ ] README first screen reads well: purpose, the NO_GO example, the four decisions with exit codes, three links.
- [ ] The demo video plays on another device or account, outside this machine.
- [ ] `python scripts/check.py` prints `Summary: PASS`.
- [ ] No `.env` or API key in any package. Run `python scripts/package.py` and check the file list.
- [ ] No AI attribution in git history.
- [ ] Submit by 8:00 PM ET on Nov 4, an hour before the deadline, then re-open the submission link to confirm.
- [ ] Rotate the API key afterwards if the project folder was ever synced online or shared with a key in it.

## Judging

The event page names two tracks. Indie is for individual builders and students and is judged on creativity,
technical ambition, and whether the project works. Startup is for teams and founders and is judged on
technical execution and whether the project holds up in production. A secondary report gives project
scoring weights of impact 30 percent, creative use of Meta AI tools 25 percent, the demo including its
video 25 percent, and technical depth and execution 20 percent. Those weights are UNVERIFIED against the
official Rules. Source: https://madrobot.blog/2026/10/03/meta-global-ai-developer-hackathon-1-million-prizes-muse-model-api/

## Owner-only blockers

- Take 28 photos of your own after the model release. Until they exist the training overlap check keeps
  GO_CANDIDATE out of reach.
- Find a second annotator.
- Choose the track, Indie or Startup.
- Read the official Rules.
- Fix GitHub billing so CI can run.
- Check the COCO photo licence before showing COCO photos publicly.

## Reference facts

- Pricing used for estimates: Muse Spark 1.3 Standard $1.25 per million input tokens and $4.25 per million
  output tokens; SAM 3.1 $2.50 per 1,000 images. Default spend cap is $5 per run.
- Keep to Meta's terms: do not share keys, do not bypass rate limits, use Standard mode, keep Meta's labels on
  real outputs, use only authorized media. The official Rules are authoritative.
