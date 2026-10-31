"""Coverage matrix: how many labeled cases exist per dataset and test condition. No model calls.

A cell is thin when it holds fewer cases than power.cases_needed(THIN_FAILURE_RATE) at the default
confidence, the failure-free cases needed to say the failure rate is below that bound.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from blindspot_ci.experiment.cases import MANIFESTS, load_named_dataset
from blindspot_ci.experiment.power import cases_needed

CORE_CONDITIONS = ("normal", "low_light", "small_object", "truncated", "lookalike", "absent")
THIN_FAILURE_RATE = 0.10
MIN_CASES_PER_CELL = cases_needed(THIN_FAILURE_RATE)
SYNTHETIC_NAMES = ("synthetic", "generated")


def build_matrix(datasets: dict[str, Any], unavailable: dict[str, str] | None = None) -> dict[str, Any]:
    """datasets maps a name to an already loaded Dataset. Only ids and counts are kept."""
    counts = {name: Counter(case.condition for case in ds.cases.values()) for name, ds in datasets.items()}
    conditions = sorted(set(CORE_CONDITIONS).union(*counts.values()))
    rows = {}
    for name in sorted(counts):
        cells = {c: counts[name][c] for c in conditions}
        rows[name] = {"synthetic": "SYNTHETIC" in datasets[name].kind.upper() or name in SYNTHETIC_NAMES,
                      "cells": cells, "total": sum(cells.values())}
    totals = {c: sum(r["cells"][c] for r in rows.values()) for c in conditions}
    empty = sorted(f"{n}/{c}" for n, r in rows.items() for c in conditions if r["cells"][c] == 0)
    thin = sorted(f"{n}/{c}" for n, r in rows.items() for c in conditions
                  if 0 < r["cells"][c] < MIN_CASES_PER_CELL)
    return {"min_cases_per_cell": MIN_CASES_PER_CELL, "conditions": conditions, "rows": rows,
            "condition_totals": totals, "empty": empty, "thin": thin,
            "unavailable": dict(sorted((unavailable or {}).items()))}


def load_matrix(only: str | None = None) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    unavailable: dict[str, str] = {}
    for name in sorted([only] if only else MANIFESTS):
        try:
            loaded[name] = load_named_dataset(name)
        except FileNotFoundError:
            unavailable[name] = "no manifest"
        except (OSError, ValueError, KeyError):
            unavailable[name] = "manifest or photos unreadable"
    return build_matrix(loaded, unavailable)


def _list(label: str, cells: list[str]) -> str:
    return f"{label}: {', '.join(cells) if cells else 'none'}"


def render(matrix: dict[str, Any], fmt: str = "text") -> str:
    conds, minimum = matrix["conditions"], matrix["min_cases_per_cell"]
    header = ["dataset", *conds, "total"]
    body = []
    for name, row in matrix["rows"].items():
        label = f"{name} (synthetic)" if row["synthetic"] else name
        cells = [f"{row['cells'][c]}{'*' if row['cells'][c] < minimum else ''}" for c in conds]
        body.append([label, *cells, str(row["total"])])
    body.append(["total", *(str(matrix["condition_totals"][c]) for c in conds),
                 str(sum(r["total"] for r in matrix["rows"].values()))])
    if fmt == "markdown":
        lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(r) + " |" for r in body]
    else:
        widths = [max(len(r[i]) for r in [header, *body]) for i in range(len(header))]
        lines = ["  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)).rstrip() for r in [header, *body]]
    lines += ["", f"A star marks an underpowered cell (fewer than {minimum} cases).",
              f"{_list('Empty cells', matrix['empty'])}. {_list('Thin cells', matrix['thin'])}."]
    if any(r["synthetic"] for r in matrix["rows"].values()):
        lines.append("Synthetic datasets are development fixtures, not real evidence.")
    for name, why in matrix["unavailable"].items():
        lines.append(f"Unavailable: {name} ({why}).")
    return "\n".join(lines)
