# Craft Anything check

This page records what Blindspot CI borrowed from Craft Anything, what was checked on 2026-11-03, and a repeatable three width check for the three public pages. It is a method note and a checklist. It does not change any score, release gate decision, or web page.

## Upstream credit

- Source: https://github.com/storytold/craft-anything
- Version checked: 0.3.0, release tag v0.3.0
- Licence: MIT OR Apache-2.0, at the user option
- Use here: method only. No upstream code, logo, image, or wording was copied into this project. Names of its steps and modes are used only to credit the source and to map the method.

## What Craft Anything does, in plain terms

Craft Anything is a Rust desktop app, command line tool, and MCP server. Its rebuild flow has four steps. Study means inspect the original from the outside or, in Deep mode, from the inside. Build means a coding agent makes a new project. Check means compare the new project with the original, for a website at three screen widths. Refine means fix the listed gaps and check again.

It has two study modes. Clean room keeps only what a visitor can see, such as screenshots, visible text, measured layout, colours, fonts, and spacing. Deep mode may also read code, files, page source, scripts, and requests. The default is Clean room.

## Mapping to Blindspot CI

| Craft Anything step | Blindspot CI equivalent | Gate or note |
| --- | --- | --- |
| Study | Serve the app in mock mode and capture each page at 1440, 768, and 390 px. Record title, headings, links, landmarks, text size, layout per width, and page height. | Advisory only. Study never changes a score. |
| Build | The existing Python and web work in this repo. A person or the assigned web worker edits web files under their own task scope. | Craft Anything did not build anything here. See the not used list below. |
| Check | First run the project gate. Then do the three width visual check in this page and compare each width only with the same width from the last accepted capture. | The project gate is `python scripts/check.py` and remains the final gate. |
| Refine | Fix only the ranked gap that the check proved, in the file scope that owns it. Serve again, capture the same three widths again, and run the project gate again. | Stop after three tries on the same failure and report the exact output, as in docs/agent-workflow.md. |

The release gate in docs/release-gate.md is a different gate. This check does not replace it, and a good visual check cannot turn a run into GO_CANDIDATE.

## What was run

All tool work was done outside the repo in a temp folder. No cargo build was run, no system dependency was installed, and no live model call was made. The Blindspot CI server ran in mock mode only.

Commands run, with outcomes:

```powershell
curl.exe -fL -o craft-anything-0.3.0-windows-x64-portable.zip https://github.com/storytold/craft-anything/releases/download/v0.3.0/craft-anything-0.3.0-windows-x64-portable.zip
```

Outcome: downloaded 65,779,321 bytes. The SHA256 matched the value in the upstream SHA256SUMS.txt file for that zip. There is no standalone Windows craft-anything-cli zip in the v0.3.0, v0.2.0, or v0.1.0 releases. The only command line zip is for macOS. The Windows portable zip does contain craft-anything-cli.exe beside the desktop app, so that file was used.

```powershell
craft-anything-cli.exe --version
craft-anything-cli.exe --help
craft-anything-cli.exe doctor
craft-anything-cli.exe commands
craft-anything-cli.exe --clean-room capabilities
```

Outcome: version printed craft-anything-cli 0.3.0. Doctor reported healthy true, found Chrome at the standard Windows path, found no AI backend, and reported that its MCP server answered. Commands listed the full tool set. Clean room capabilities reported 315 tools and refused the tools that look inside a target.

```powershell
python -m blindspot_ci.cli serve
curl.exe -s http://127.0.0.1:8000/health
```

Outcome: health returned status ok with provider mock. The pages at /, /app, and /guide each returned HTTP 200.

One command line call can open a page, but the next command line call cannot capture it. The exact error was: no website is open, and the tool explained that each CLI command starts its own browser and closes it when it ends. The fix used here was one MCP session for each open, capture, and close sequence, still in Clean room and still with no builder.

MCP tools used in that one session: web_site_open, web_site_capture, and web_site_close, for each of /, /app, and /guide, at widths 1440, 768, and 390. Outcome: nine full page screenshots and three capture folders, each with a capture.json file and a README summary, saved in temp only. Evidence ids and files stay out of this repo because they are working material, not results.

```powershell
craft-anything-cli.exe --clean-room web-pixels-compare --json @params.json
```

Outcome: comparing the home 1440 screenshot with itself gave 0 differing pixels and layout similarity 1.0. Comparing the home 1440 screenshot with the home 390 screenshot gave a difference fraction of about 0.585. That second number is expected and proves only that pixel compare must be same width to same width.

## Findings ranked

These are study findings from the captures above. No web file was changed for this task, because another worker owns those files.

1. Highest: the app page at /app reports nine empty level 3 headings and six unnamed buttons in the capture accessibility outline. Checking the page source by eye shows those headings and controls belong to the collapsed advanced tools section near the end of the page, so the tool is listing hidden content as if it were empty. That part is a tool limit, not proof of a visible bug. The real gap beside it is that evidence card titles are bold text in a figure caption, not headings, so heading navigation skips each failed photo. The web worker should check heading order and control names with that section both closed and open before changing anything.
2. High: /app is much longer on a phone. Page height was 4551 px at 1440, 5499 px at 768, and 8385 px at 390. The evidence grid goes from three per row, to two, to one. The decision banner is still near the top, which is good, but a reader scrolls a long way to reach the collapsed sections and footer. The check below asks for the first phone screen to show the decision and the first fix.
3. Medium: one capture is one state only. The capture itself warns that menus, dialogs, and content behind interactions are not opened. On these pages that means the collapsed All tests, Details, and Run a new check sections on /app, the Show all failed photos control on /app, and the Open the playground control on /guide were not exercised by the capture. The manual checklist below opens each one at each width.
4. Medium: do not read the capture column field as rendered width. At 390 the capture still lists a content column max of 1120 px and section max values above the screen width, while the rendered column widths fit at 390 or 350 px and no page showed sideways scroll at any width. A max width token is not an overflow. Flag overflow only from rendered width or from a visible sideways scroll.
5. Low: type scale differs by page. The capture reports body text at 17 px on /guide and 14 px on / and /app. At 1440 the first heading is 48 px on /, and 34 px on /app and /guide. This may be a deliberate reading size for the guide, but it should be a choice on record, not an accident found by a tool.
6. Low: tool counts need reading, not copying. The capture counts zero images and zero forms on all three pages. That counts only image elements and form elements. The /app evidence is drawn as inline SVG with a lazy image attempt on a blank panel, and its controls are buttons, selects, inputs, and a text area outside a form. Zero here does not mean missing photos or missing controls.
7. Note on nav: the nav bar is 56 px high at 1440 and 768, and 72 px high at 390 on all three pages, where the links wrap to a second line under the brand. No overlap was seen in the screenshots. Keep this as a regression check, because a longer brand or a fourth link would break it first.

Positive checks: no sideways scroll was reported at any width on any page, page titles were present and distinct, language was en, landmarks included navigation, main, and content info, and images without alt text were reported as zero.

## Follow-up fixes after the web check

The study above ran at commit 3486bbe. On 2026-11-03 the web worker fetched the latest origin main again and fixed the two top findings in the web files that own them. The deployment files were not touched.

What changed on /app:

- Each failed photo title in Evidence is now a real level 3 heading inside its figure caption, under the level 2 Evidence heading. Heading navigation now reaches every failed photo. Before this fix the titles were bold text only.
- The eight level 3 headings that sat inside the collapsed Details and Advanced tools sections are now styled title text, not headings. Their sections are still named by the visible summary controls, and every control inside was checked with the sections open. With the sections open there were no unnamed controls and no control smaller than 24 px. With the sections closed a visitor sees no empty heading, which matches what the capture tool reported.
- The Photos, Max tests, and Photo selects now name their labels with an explicit for link to the control id. The visible layout did not change.
- Evidence now shows the first 6 failed photos and keeps the named Show all control for the rest. Page height on /app went from 4551 to 3345 px at 1440, from 5499 to 3732 px at 768, and from 8361 to 5514 px at 390. The decision and Download report stay in the first phone screen.
- On the home page the See this result link now has a 24 px minimum height. It measured 21 px before.

What was rechecked after the fix:

- No sideways scroll at 1440, 768, or 390 on /, /app, or /guide. Home and guide page heights did not change.
- Heading order is one level 1 heading, then level 2 sections, then the evidence level 3 headings. No empty visible heading on any page at any width.
- Lighthouse accessibility scored 100 on /, /app, and /guide, with no failing audit. Contrast was computed from the shared style sheet. Every text pair is at least 4.5 to 1 in light and dark mode, and the focus outline colour is at least 3 to 1 against the page ground.
- The guide body size difference in finding 5 was left unchanged. It reads as a deliberate reading size and stays on record as a choice, not a defect.

Nothing else in the ranked list changed. Pixel compare is still same width only, and the repeatable check below is still the way to rerun this.

## Repeatable three width check

Use this before the hackathon deadline and after any web change. Timebox tool attempts to 45 minutes. If the Craft Anything CLI does not run in that time, record the exact error, skip to the manual fallback in the next section, and do not build the Rust workspace.

### Setup

```powershell
python scripts/check.py
python -m blindspot_ci.cli serve
curl.exe -s http://127.0.0.1:8000/health
```

The gate must print Summary: PASS. Health must show provider mock. If either fails, stop and fix that first. A visual pass cannot cover a gate fail.

Serve on 127.0.0.1 port 8000 only. Do not use a public deployment for this check, because the app has no sign in.

### Widths

| Name | Width in px | Why this width |
| --- | --- | --- |
| Desktop | 1440 | The wide check used by Craft Anything for websites |
| Tablet | 768 | The middle check, where grids often change count per row |
| Phone | 390 | The narrow check, where nav wrap and long pages show first |

Compare desktop with desktop, tablet with tablet, and phone with phone. Never score a width against a different width.

### Common checks at every width

Do these for /, then /app, then /guide, at 1440, then 768, then 390.

1. The page loads with HTTP 200 and the title names the page. Home title starts with BLINDSPOT CI. The /app title starts with Result. The /guide title starts with How it works.
2. There is no sideways scroll. If a scrollbar or clipped right edge appears, note the width, the page, and the first element that crosses the edge.
3. The nav shows the brand and the three links Home, Example result, and How it works. The current page link is marked. At 390 the nav may take two lines and reach about 72 px high, with no overlap and no cut text.
4. The first screen shows what the page is for, without opening any collapsed section. Home shows the ship question. The /app page shows the result name and the decision. The /guide page shows How BLINDSPOT CI works and The problem.
5. Headings go in order with one first level heading. Note any empty heading and any place where a visible title is not a heading.
6. Every link and button can be reached and read. Note any control with no visible or accessible name, first with collapsed sections closed, then with them open.
7. Text does not overlap, clip, or shrink below the size on the last accepted capture. Note the page, width, and section name for any change.
8. The footer still says this is a bounded evaluation and not a safety approval.
9. Save one full page screenshot per page per width in temp. Keep them out of git. Name them by page and width so a later run can compare the same width.

### Home page checks for /

1. At 1440 the first heading is about 48 px, the three How a check works boxes sit in one row, and A real result shows the Do not ship yet card with See the full result.
2. At 768 the first heading steps down, near 38 px, and the three boxes still sit in one row without squeezing text.
3. At 390 the first heading is near 30 px, the three boxes stack in one column, and page height grows from about 1613 px to about 2190 px. A growth far beyond that range needs a reason on record.
4. The second result card for video frames is present and its See this result link goes to /app.
5. What this is not is present near the end and says a person always decides.

### Result page checks for /app

1. At 1440 the first heading is about 34 px. Why, What to fix, and Evidence are present in that order. The evidence grid is three per row.
2. At 768 the evidence grid is two per row and page height is near 5499 px. The Why table fits with no sideways scroll inside the page. If the table itself scrolls, that scroll area is labelled and reachable by keyboard.
3. At 390 the evidence grid is one per row and page height is near 8385 px. The decision and Download report are still in the first screen area, and Show all failed photos is a clear control about 44 px high.
4. Press Show all failed photos at each width. The count shown matches the failed count in the intro line. In the checked run that count was 13.
5. Open All tests, then Details, then Run a new check and advanced tools, at each width. Headings and controls inside must have names when open. This is the manual check that covers finding 1 and finding 3 above.
6. Each evidence card names the photo, the outcome in words, and which box is the person box and which is the model box. A blank panel must say the photo is not in this download.
7. The mock mode line near the footer is present when serving in mock mode. Do not present any result on this page as a new live result.

### Guide page checks for /guide

1. At 1440 the first heading is about 34 px and the sections run in order: The problem, The four steps, What the four decisions mean, What we have not tested, Real long video test, Glossary, and Try the overlap score.
2. Body text is larger here than on the other pages in the checked capture, 17 px against 14 px. Confirm that stays a deliberate reading choice and that line length stays readable at 1440.
3. At 768 page height stays near 2631 px, close to the desktop height. At 390 it grows to near 3206 px with sections in one column and no sideways scroll.
4. Open the playground under Try the overlap score at each width. The control opens, its content fits the width, and closing it returns focus to the control.
5. The four decisions are named with both the plain wording and the code in brackets, and Passed every check still says a person still decides.

### Pass and fail rules for this visual check

- Pass: the project gate passes, no sideways scroll at any width, no empty visible heading, no unnamed visible control, the first screen job of each page is clear at 390, and every collapsed section was opened once at each width.
- Fail: any item above fails. Record page, width, section, and what was seen. Fix only that item in its owning scope, then repeat the full check for that page at all three widths.
- Not a fail by itself: a page height change after a real content change, a max width token above the screen width, or a zero image or form count from the capture tool. Each still needs a one line reason in the work report.

## Manual fallback if the CLI does not run

Record the exact command, the exact error text, and the exit code. Then do the same check by hand:

1. Serve in mock mode as above.
2. Open /, /app, and /guide in a browser at window widths 1440, 768, and 390.
3. Take one full page screenshot per page per width and save them in temp with page and width in the name.
4. Work through the common, home, result, and guide lists above by eye and by keyboard.
5. Write down page height, heading order, grid count per row, and any unnamed control, per width.

The fallback gives the same ranked findings list. It loses the measured layout and colour tokens, so say that in the report.

## What Craft Anything was and was not used for

Used for:

- Reading the public repo page and release list to learn the workflow, modes, and website check widths.
- Running the prebuilt Windows CLI from temp for version, doctor, commands, and Clean room capabilities.
- One Clean room MCP session to open and capture /, /app, and /guide at three widths, with evidence kept in temp.
- Pixel compare on two pairs of saved screenshots to prove that compare is same width only.

Not used for, and why:

- No rebuild or Build step. Building needs a coding agent on this machine. The task said not to use Claude Code, which is the first supported builder, and a rebuild would make a new project folder instead of checking this Python app. It would also spend agent quota that the owner said is exhausted.
- No rebuild_check. That tool checks a Craft Anything build against its original inside a build session. There was no such build, so there was nothing honest for it to check.
- No Deep mode. Blindspot CI is our own app, but the point of this trial was the visitor view. Deep mode would read page source, scripts, and requests, which adds no value for a visual width check and would blur the line between study and our own source reading, which we can already do in the repo.
- No desktop app, no MCP setup registration, and no settings change. Doctor noted agent apps as installed but not connected. Connecting them would change files in other apps for no gain in this check.
- No Ghidra or other optional engines, and no cargo build. Doctor listed them as optional and not found. This is a Python and web check, and the task set a 45 minute tooling timebox with a prebuilt only rule.
- No asset generation and no paid call of any kind. The server stayed in mock mode.
- No upstream code, logo, image, or text copied. The licence would allow code use with credit, but this project needs a checklist, not a Rust engine.

## Where this sits before the deadline

Run the project gate first, then this visual check, then fix only proven gaps. For the Nov 4 8pm ET deadline, this check is a half hour task when the CLI already runs, and a one hour task on the manual fallback. Anything that needs a web file change goes to the worker who owns those files, with page, width, and section named.

## Source

Craft Anything, version 0.3.0: https://github.com/storytold/craft-anything - dual licensed MIT OR Apache-2.0. Checked 2026-11-03 in Clean room mode only.
