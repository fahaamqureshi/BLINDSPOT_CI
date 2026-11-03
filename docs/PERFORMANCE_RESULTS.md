# Local performance results

## Current repeat measurement

A new isolated Windows Python 3.13.15 mock audit measured startup 1037.01 ms, five-case evaluation 29.97 ms, cached evaluation 17.66 ms, gate 8.48 ms, Markdown export 2.12 ms, twenty reads with four workers 31.37 ms total, and restart 1038.07 ms. All twenty reads returned 200, all five repeat steps hit cache, and the saved run and export survived restart. Paid calls: zero. Raw output: artifacts/submission-audit/http-audit-output.json. These are single local smoke measurements, not percentile latency or hosted load results. Peak memory remains unmeasured.

The earlier measurements below are historical repetitions, not additional independent performance samples.

Date: 2026-11-03. Windows, Python 3.13.15, existing virtual environment, loopback Uvicorn. Single measured smoke run after development, no hosted measurement and no statistical latency study. Reproduce with python scripts/audit_mock.py. Raw evidence: artifacts/final-audit/evidence.json, run 336018068fb54ae7.

| Operation | Measured milliseconds |
| --- | --- |
| Startup to health response | 1042.62 |
| Five-case mock evaluation | 30.19 |
| Cached five-case evaluation | 20.18 |
| Release gate HTTP request | 9.27 |
| Markdown report request | 1.85 |
| Twenty reads, four workers, total | 29.86 |
| Restart to health response | 1038.93 |

All 20 concurrent reads returned 200. Five repeated downloads matched. Zero evaluation errors across five fixture cases; one deliberately wrong fixture answer is an expected scored failure. Second run used five cached answers out of five. Summaries were identical. Five-case planner iteration count was five; recovery selected an existing alternate-view image. No paid model request was made and fixture estimated cost was USD 0.00. This says nothing about Meta billing or live latency.

Upload latency, real image processing latency, server peak memory, hosted throughput and browser cancellation latency were NOT_MEASURED. There is no photo upload endpoint or browser cancellation control. Python bounded-loop cancellation is covered by existing tests. Do not substitute these small local measurements for production capacity estimates.
