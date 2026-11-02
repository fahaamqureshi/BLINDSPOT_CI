# Production readiness

BLINDSPOT CI is a local-first evaluation tool. It runs on your machine with your own key. A public
server is safe only as a scripted demo with no key. This page is the readiness record: what was
checked, what was fixed and what is still open. How to deploy the public mock demo lives in one
place, `docs/free-deployment.md`. Local run steps live in `README.md`.

The Docker image was written but not built or run on the development machine, because Docker is not
installed there. Build it once on a machine with Docker before relying on it.

## Settings that matter

| setting | effect |
| --- | --- |
| `BLINDSPOT_PROVIDER` | `mock` (default, free) or `meta` (live) |
| `LIVE_API_ENABLED` | must be `true` for any paid call, even with a key |
| `MODEL_API_KEY` | your key. Keep it in `.env` or the host's secret store, never in an image |
| `BLINDSPOT_BUDGET_USD`, `BLINDSPOT_MAX_CALLS` | per-run caps. A server-wide cap also applies to live spend |
| `BLINDSPOT_HOST`, `BLINDSPOT_PORT` | bind address. Default 127.0.0.1:8000 |
| `BLINDSPOT_ALLOWED_HOSTS` | extra host names the server will answer. Loopback is always allowed |

The server refuses to start on a non-loopback address while `LIVE_API_ENABLED=true`. A public server
must stay in mock mode, because it has no sign-in and anyone who reaches it could spend your key.

## What was reviewed

Three independent read-only reviews ran on 2026-10-31: security, correctness and robustness, and
web accessibility and honesty of copy. Their findings were checked against the code before any fix.

Fixed:
- A web page in your browser could trigger paid calls or rewrite labels. Host and Origin checks now
  apply to the main app and the labeling tool.
- Live calls could start through `/api/run` without `LIVE_API_ENABLED`. Now guarded.
- Repeated experiment runs could each spend a full budget. Live spend now counts against one
  server-wide cap, and the cap is thread-safe.
- A run replayed entirely from cache was saved as LIVE_META. The mode now follows what the steps used
  (LIVE_META, CACHE_LIVE_META or MIXED_CACHED_AND_LIVE_META).
- Client errors such as 400 and 404 were retried and billed up to three times. A date in Retry-After
  crashed the retry. Both fixed.
- Variants already paid for were lost when a later one failed. They are now kept.
- Torn JSON files from concurrent writes. Writes are atomic and read-modify-write is locked. A
  damaged cache file counts as a miss.
- Voice uploads were read into memory before the size check, and a non-WAV file was charged.
- Reviewer notes and provenance text reached the Wonder audit prompt unclean. Text is now shortened,
  stripped of control characters and marked as untrusted. Audit text sits in a fenced block in the card.
- Large photos made `noise` corruption slow, and every request re-hashed every image. Noise work is now
  bounded, and an unchanged dataset is fingerprinted by file size and time instead of re-hashed (a
  changed image is still caught). A true or false value is no longer accepted as a box number, and a
  malformed manifest answers with a clear message.
- The data download scripts now accept https only, cap photo size and allow only plain image ids.
- The stylesheet was missing from the package data, so an installed copy had no styling.
- Accessibility: labels, keyboard operation of the box playground and the labeler, live regions,
  contrast in light and dark mode, skip links, clear messages when the server is down.
- Copy: the overview page now states the unadjusted 20 of 24, that two labels were set aside by one
  person, that two sets ran in a scripted order, and that the 22 corruption tests came from five
  photos that had already passed.

## Still open

- No sign-in and no rate limit. Do not expose a live key behind this app.
- Live access is intermittent. On 2026-10-31 every model answered `model_not_found` for a while, then worked
  (a fresh live check passed for the agent, SAM 3.1, Muse Wonder and Muse Image). On 2026-11-01 it failed the same
  way and `/models` returned an empty list. The key is valid. Run `python -m blindspot_ci.cli diagnose` before any
  live run. Saved runs and cards are unaffected.
- The live cache key has no prompt version, on purpose: adding one would make every saved live answer
  miss and cost money to reproduce. If the SAM request format changes, delete `.blindspot-cache` before
  a live run. The mock key already follows the scripted fixtures.
- Run files, cache files and the provenance log grow without limit. Clear `artifacts` and
  `.blindspot-cache` when you want space back.
- The Docker image has not been built or run yet. Docker is not installed here and CI does not build it. CI runs ruff and pytest on every push and pull request.
