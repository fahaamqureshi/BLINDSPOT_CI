# Local performance results

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
