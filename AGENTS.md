# BLINDSPOT CI agent guide

BLINDSPOT CI is a Python and FastAPI evaluation tool for vision models.
It uses person-labeled cases, a bounded planner, and plain Python scoring.
It is an evaluation harness, not a benchmark or a safety approval.

## Setup and checks

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m ruff check blindspot_ci scripts tests
$pytestTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("blindspot-ci-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $pytestTemp | Out-Null
python -m pytest --basetemp="$pytestTemp" -p no:cacheprovider
```

Use mock mode only. The final gate before reporting is `python scripts/check.py`.
That script may be absent on this branch, which is expected.

## Layout

`blindspot_ci/` package: providers, experiment loop, scoring, API, and web UI.
`scripts/` dataset, live helper, packaging, and check scripts.
`tests/` pytest suite. `fixtures/` deterministic mock answers.
`datasets/` manifests and photos. `docs/` design, results, and readiness notes.

## Hard rules

1. Never add AI attribution, co-author lines, or generated-with text.
2. In README.md and Markdown files under docs use plain wording. Do not use em dashes, ellipses, asterisks, or emojis.
3. Never read, print, commit, or expose `.env` or an API key. Never make live API calls or spend money.
4. Mock and fixture results are not model performance. Labels come from a person, never a model.
5. Make surgical changes only in the assigned scope. Report unrelated problems without fixing them.
6. Do not push or merge. Commit on the feature branch using the existing git identity.
7. Keep local `main` commit `56cf811` in the branch. Rebase onto `main` if it is absent.

## Definition of done

The scoped files are complete, the required checks pass, forbidden Markdown characters are absent,
and the final report lists changed files, exact check output, factual evidence, open issues, branch,
and commit SHA. Git history contains no AI attribution.
