# Security audit

Date: 2026-11-03. Scope: non-destructive local checks in mock mode. No dotenv file, API key, private image collection or credential value was opened or printed. This is not a penetration-test certification.

| Check | Result | Evidence |
| --- | --- | --- |
| Host guard | PASS | HTTP evil.invalid Host refused with 403; exact-host regression tests |
| Cross-origin mutation | PASS | HTTP experiment POST with foreign Origin refused with 403 |
| Path traversal | PASS | Existing image path and run-ID tests reject escaping the dataset/run root |
| Upload limits | PARTIAL | Local importer validates decoded size and image content; audio cap tests; no photo upload endpoint |
| Label integrity | PASS | Hash, box, visibility and provenance tests; planner cannot call a label editing tool |
| Tool arguments | PASS | Invalid tool/case and array/null regression tests; bounded loop schemas |
| Live lockout | PASS | Both enabling conditions required; intercepted tests, no paid call |
| Secret packaging | PASS | Final gate scans allowlisted distributable files and reports names only |
| Authentication | NOT_IMPLEMENTED | Local single-user application, no tenant isolation |
| Persistence | PASS | Atomic JSON helpers, run/card reopen after process restart |

.gitignore excludes .env, local artifacts, caches and private dataset folders. Packaging allowlists files and omits private datasets. The scan is pattern-based and cannot prove that every possible credential has been removed from all history. The final attribution check scans main..HEAD, not every historical commit. No full-history secret certification is claimed.

Open P1: experiment routes check the shared live cap before a run and charge after it, while each run owns a separate guard. This does not provide an atomic server-wide reservation across concurrent runs. Retries and listed-price estimates are also not a guarantee of exact billed consumption. Do not use this as a public live inference service. This audit kept the application in mock mode; no budget defect was exercised against a paid endpoint.

Open P2: arbitrary imported text can still be semantically adversarial despite length/control filtering. Tool allowlists and scorer separation limit its authority; offline injection tests are not proof of immunity for a live language model. Image MIME upload matrix is not applicable to the CLI path; unsupported extensions and corrupt image bytes have local validation coverage.
