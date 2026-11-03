# Developer guide

BLINDSPOT CI is a local evaluation tool. It compares vision predictions with human references and preserves evidence for review. Start with scripted practice before configuring a real model.

## Install from source

Use Git and Python 3.11 or newer. Follow the platform-specific virtual-environment installation in the [README](../README.md#quick-start). The package is not claimed to be published on PyPI.

## Create your workspace

Use the installed blindspot command, or replace it with python -m blindspot_ci.cli from the same virtual environment.

```bash
blindspot init ../blindspot-workspace
blindspot --workspace ../blindspot-workspace doctor --mock
blindspot --workspace ../blindspot-workspace serve --mock
```

Open http://127.0.0.1:8000/app. Run five practice tests and inspect the deliberate miss. The expected result is three passes, one failure, one unknown and DEMO_ONLY. These are software fixtures, not model-performance measurements.

The workspace owns its datasets, saved runs, cache and provenance. The application and its installed package stay separate. You can start from another working directory by passing an absolute workspace path. Initialization copies only public practice assets, does not read credentials and refuses to overwrite an unrecognized non-empty folder. Repeating init on an initialized workspace preserves its files.

The --mock flag disables dotenv loading, forces the mock provider, scripted planner and synthetic dataset, and disables live calls for that process. It does not rewrite your saved configuration. Explicit run, cache and provenance environment overrides take precedence over workspace defaults; doctor shows the resolved locations.

## Check setup without making model calls

```bash
blindspot --workspace ../blindspot-workspace doctor --mock --json
```

Doctor validates configuration, the selected dataset and images, and basic storage permissions. It makes zero network calls and does not create an evaluation run. It does not test model access, guarantee future disk availability or measure a model. Exit code 0 means the checks passed; 2 means local setup needs attention.

## Run, reopen and export

```bash
blindspot --workspace ../blindspot-workspace experiment --mock --steps 5
```

The command prints the saved run identifier. Replace RUN_ID below with that identifier:

```bash
blindspot --workspace ../blindspot-workspace card --run RUN_ID --out review.md
blindspot --workspace ../blindspot-workspace release-gate --run RUN_ID
```

Release-gate exit codes are policy results: 0 GO_CANDIDATE, 1 NO_GO, 2 NEEDS_REVIEW, 3 DEMO_ONLY and 4 input error. An experiment exits with an error when execution fails; finding a scored model failure is different from an execution error.

Saved runs also appear in the browser. Reviewer notes do not change scores. The API reference is at http://127.0.0.1:8000/docs while the server runs. The [API contracts](API_CONTRACTS.md) explain requests, source modes and errors.

## Add human-labeled photos

```bash
blindspot --workspace ../blindspot-workspace label --folder /path/to/photos --annotator Reviewer --out labels.json
blindspot --workspace ../blindspot-workspace import-photos labels.json --dataset real
```

Use a real reviewer identity in your own workflow. The labeler opens on port 8001. Source image paths in a labels file may be absolute or relative to that labels file. Imports validate references, target conflicts and encoded image sizes before writing images. Unexpected storage failures still require checking the local workspace before retrying; an import is not a database transaction.

The real collection is now available in the browser dataset selector. To validate it without inference, select BLINDSPOT_DATASET=real in your environment and run doctor without --mock. Doctor itself never makes model calls. Running custom cases with the mock provider does not simulate a real model and may have no matching fixture answer.

See [dataset preparation](dataset.md) for label format, condition names, provenance and adjudication. Unknown references stay unscored. Generated variants need human review before their references can support accuracy claims.

## Configure an authorized real evaluation

Live operation is separate from the plug-and-play practice route. It requires the live dependency extra, your authorized provider access, explicit LIVE_API_ENABLED=true and an explicit provider/planner choice. Credentials are local secrets and are not part of the workspace template or repository. Keep the service bound to loopback and use spending controls.

The provider interface is [VisionProvider](../blindspot_ci/providers/base.py). Existing adapters return [ProviderResult](../blindspot_ci/models.py); Python scoring receives references separately. Extending to another provider requires correct source attribution, coordinate handling, caching identity, cost accounting and regression coverage. No arbitrary-provider compatibility is claimed without those checks.

## Storage and environment reference

| Setting | Default or effect |
| --- | --- |
| BLINDSPOT_WORKSPACE | Explicit workspace root; --workspace selects it for a CLI process |
| BLINDSPOT_RUNS_DIR | Workspace artifacts/runs, otherwise artifacts/runs relative to the working directory |
| BLINDSPOT_CACHE_DIR | Workspace .blindspot-cache, otherwise .blindspot-cache |
| BLINDSPOT_PROVENANCE_PATH | Workspace artifacts/provenance.jsonl, otherwise artifacts/provenance.jsonl |
| BLINDSPOT_DATASET | synthetic by default; --mock selects synthetic |
| BLINDSPOT_PROVIDER | mock or meta |
| BLINDSPOT_PLANNER | heuristic, mock or muse; heuristic and mock are scripted policies |
| BLINDSPOT_MIN_IOU | 0.35; must be finite and between 0 and 1 |
| LIVE_API_ENABLED | false by default; true or false, also 1 or 0 |
| DOTENV_DISABLED | 1 disables dotenv loading; --mock sets this before configuration loads |

For Python or an ASGI server, set BLINDSPOT_WORKSPACE before importing application modules. Dataset and fixture locations are bound when those modules load; change workspaces by starting a new process. Importing Settings alone is not a sandbox for arbitrary third-party code.

The checkout-based commands remain supported for existing users. Workspaces provide explicit storage outside the source and site-packages directories. Never publish a private workspace as source code.

## Change ports and verify changes

```bash
blindspot --workspace ../blindspot-workspace serve --mock --port 8055
```

Host and port also accept BLINDSPOT_HOST and BLINDSPOT_PORT. An invalid port produces a command-line error. Serving a live-enabled process on a public bind address is refused.

Run the [completion and packaging checks](../README.md#development-checks) before delivery. The installed-wheel verification includes workspace creation, offline diagnostics and an evaluation outside the checkout. The [developer-readiness audit](DEVELOPER_READINESS_AUDIT.md) records the fixes and remaining boundaries.
