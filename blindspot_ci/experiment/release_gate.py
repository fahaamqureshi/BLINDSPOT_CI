"""Release Gate: a conservative decision on whether saved evidence supports advancing toward deployment.

Reads one saved run report, an optional policy and an optional agreement report. No model calls.
Mock, fixture, synthetic, generated and corrupted evidence can never produce more than DEMO_ONLY.
GO_CANDIDATE is never a deployment approval or a safety certification.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from blindspot_ci.experiment.cluster_ci import cluster_interval, group_key
from blindspot_ci.experiment.coverage import DERIVED_NAMES, SYNTHETIC_NAMES, condition_family
from blindspot_ci.experiment.power import cases_needed
from blindspot_ci.experiment.runner import RUN_ID
from blindspot_ci.experiment.scoring import ERROR, PASS, UNKNOWN, wilson_interval

GO_CANDIDATE, NO_GO, NEEDS_REVIEW, DEMO_ONLY = "GO_CANDIDATE", "NO_GO", "NEEDS_REVIEW", "DEMO_ONLY"
EXIT_CODES = {GO_CANDIDATE: 0, NO_GO: 1, NEEDS_REVIEW: 2, DEMO_ONLY: 3}
LIVE_MODES = ("LIVE_META", "CACHE_LIVE_META", "MIXED_CACHED_AND_LIVE_META")
NOT_APPROVAL = "Human review is mandatory. GO_CANDIDATE is not a deployment approval or safety certification."
DEFAULT_POLICY: dict[str, Any] = {
    "policy_version": "1",
    "required_conditions": ["normal", "low_light", "small_object", "truncated", "absent"],
    "min_judged_cases": 10,
    "min_pass_rate": 0.90,
    "min_cases_per_condition": cases_needed(0.10),
    "max_unscored_share": 0.05,
    "min_second_annotator_share": 0.30,
    "min_kappa": 0.60,
    "require_no_training_overlap": True,
}
BOOL_KEYS = ("require_no_training_overlap",)
LIKELY_SEEN, UNKNOWN_OVERLAP, NOT_SEEN = "likely_seen", "unknown", "not_seen"
# Unverified. Taken from summaries of the SAM 2 and SAM 3 papers; the owner must check the papers.
# not_seen is only for photos the owner took after the model release, and no id is listed here
# because no manifest in this repo records who took the photos. Unlisted datasets count as unknown.
TRAINING_OVERLAP: dict[str, str] = {
    "davis-2017-frames": LIKELY_SEEN,
    "coco-val2017": UNKNOWN_OVERLAP,
    "open-images-v7-validation": UNKNOWN_OVERLAP,
    "open-images-v7": UNKNOWN_OVERLAP,
    "open-images-v7-hard": UNKNOWN_OVERLAP,
    "mot20-long": UNKNOWN_OVERLAP,
}
_EXTRA_CAP = 2000


def load_policy(path: str | Path | None) -> dict[str, Any]:
    """DEFAULT_POLICY overridden by a JSON file. Unknown keys are rejected."""
    policy = {**DEFAULT_POLICY, "required_conditions": list(DEFAULT_POLICY["required_conditions"])}
    if path is None:
        return policy
    override = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(override, dict):
        raise TypeError("policy file must hold a JSON object")
    unknown = sorted(set(override) - set(DEFAULT_POLICY))
    if unknown:
        raise ValueError(f"unknown policy keys: {', '.join(unknown)}")
    policy.update(override)
    if policy["policy_version"] != DEFAULT_POLICY["policy_version"]:
        raise ValueError(f"unsupported policy_version {policy['policy_version']!r}")
    req = policy["required_conditions"]
    if not isinstance(req, list) or not req or not all(isinstance(c, str) for c in req):
        raise ValueError("required_conditions must be a non-empty list of names")
    for key in BOOL_KEYS:
        if type(policy[key]) is not bool:
            raise ValueError(f"policy key {key} must be true or false")
    for key in DEFAULT_POLICY:
        if key not in ("policy_version", "required_conditions", *BOOL_KEYS) and (
                isinstance(policy[key], bool) or not isinstance(policy[key], int | float)):
            raise ValueError(f"policy key {key} must be a number")
    return policy


def _demo_reason(run: dict[str, Any]) -> str | None:
    mode = str(run.get("mode", ""))
    dataset = run.get("dataset") or {}
    kind, ds_id = str(dataset.get("type", "")).upper(), str(dataset.get("id", "")).lower()
    if "MOCK" in mode.upper() or "FIXTURE" in mode.upper():
        return f"run mode {mode} is mock or fixture output, not model performance"
    if any(n in ds_id for n in SYNTHETIC_NAMES + DERIVED_NAMES) or any(
            n.upper() in kind for n in (*SYNTHETIC_NAMES, *DERIVED_NAMES)):
        return f"dataset {dataset.get('id')} ({dataset.get('type')}) is synthetic, generated or corrupted"
    if not kind.startswith("HUMAN_LABELED"):
        return f"dataset type {dataset.get('type')!r} is not human-labeled real photos"
    return None


def _lower(passed: int, scored: int) -> float:
    ci = wilson_interval(passed, scored)
    return ci[0] if ci else 0.0


def _extra_needed(passed: int, scored: int, policy: dict[str, Any]) -> int:
    """Smallest count of further passing cases that meets the sample size and Wilson bar."""
    for extra in range(_EXTRA_CAP + 1):
        if scored + extra >= policy["min_cases_per_condition"] and \
                _lower(passed + extra, scored + extra) >= policy["min_pass_rate"]:
            return extra
    return _EXTRA_CAP


def _check(name: str, status: str, detail: str, fix: str | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _usable_cluster_interval(groups: dict[str, list[bool]]) -> tuple[list[float] | None, str | None]:
    """Use a cluster interval only when enough repeated groups give it width."""
    if not groups:
        return None, None
    interval = cluster_interval(groups)
    if interval is None or len(groups) < 5 or interval[0] == interval[1]:
        return None, "by clip: n/a (too few clips to estimate)"
    return interval, None


def evaluate(run: dict[str, Any], policy: dict[str, Any], agreement: dict[str, Any] | None = None,
             run_sha256: str | None = None) -> dict[str, Any]:
    dataset = run.get("dataset") or {}
    steps = run.get("steps") or []
    hashes = {s["image_sha256"] for s in steps if s.get("image_sha256")}
    trace = {"run_id": run.get("id"), "dataset_id": dataset.get("id"), "dataset_type": dataset.get("type"),
             "mode": run.get("mode"), "run_sha256": run_sha256, "policy_version": policy["policy_version"],
             "distinct_image_hashes": len(hashes) if hashes else None}
    base = {"policy": policy, "traceability": trace, "checks": [], "conditions": {}, "failing": [],
            "next_experiments": [], "notice": NOT_APPROVAL}
    why = _demo_reason(run)
    if why:
        return {**base, "decision": DEMO_ONLY, "reason": why,
                "next_experiments": ["run a live experiment on a human-labeled real dataset, then gate that run"]}

    counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"passed": 0, "scored": 0, "groups": defaultdict(list)})
    unscored = 0
    for step in steps:
        status = (step.get("outcome") or {}).get("status")
        if status in (UNKNOWN, ERROR):
            unscored += 1
        elif status == PASS or str(status).startswith("FAIL"):
            condition = condition_family((step.get("case") or {}).get("condition", "other"))
            cell = counts[condition]
            cell["scored"] += 1
            cell["passed"] += status == PASS
            group = group_key(run, step)
            if group is not None:
                cell["groups"][group].append(status == PASS)
    checks: list[dict[str, Any]] = []
    no_go: list[str] = []
    review = False
    configured = run.get("configured_case_ids")
    if configured is not None:
        tested = [(s.get("case") or {}).get("id") for s in steps]
        complete = set(tested) == set(configured) and len(tested) == len(set(tested))
        review |= not complete
        checks.append(_check("fixed suite coverage", "PASS" if complete else "FAIL",
                             f"{len(set(tested) & set(configured))}/{len(configured)} configured cases tested",
                             "run every configured case once before considering release" if not complete else None))
    for cond in sorted(policy["required_conditions"]):
        passed, scored = counts[cond]["passed"], counts[cond]["scored"]
        ci = wilson_interval(passed, scored)
        cluster_ci, cluster_note = _usable_cluster_interval(counts[cond]["groups"])
        rate = passed / scored if scored else None
        condition_report = {"passed": passed, "scored": scored, "pass_ci95": ci}
        if cluster_ci is not None:
            condition_report["cluster_ci95"] = cluster_ci
        base["conditions"][cond] = condition_report
        shown = f"{passed}/{scored}" + (f", Wilson 95% [{ci[0]}, {ci[1]}]" if ci else "")
        if cluster_ci is not None:
            shown += f", by clip [{cluster_ci[0]}, {cluster_ci[1]}]"
        elif cluster_note is not None:
            shown += f", {cluster_note}"
        if scored and scored >= policy["min_judged_cases"] and rate < policy["min_pass_rate"]:
            no_go.append(cond)
            base["failing"].append(f"{cond}: {shown}, pass rate {rate:.3f} below {policy['min_pass_rate']}")
            checks.append(_check(f"pass rate {cond}", "FAIL", f"{shown}, bar {policy['min_pass_rate']}",
                                 f"fix the {scored - passed} failing {cond} cases, then re-run on fresh photos"))
        else:
            status = "NA" if rate is None else "PASS" if rate >= policy["min_pass_rate"] else "FAIL"
            note = f", under {policy['min_judged_cases']} scored so not a NO_GO" if status == "FAIL" else ""
            checks.append(_check(f"pass rate {cond}", status, f"{shown}, bar {policy['min_pass_rate']}{note}"))
        more = _extra_needed(passed, scored, policy)
        fix = f"collect {more} more {cond} photos (all must pass to meet the bar)"
        thin = scored < policy["min_cases_per_condition"]
        review |= thin
        checks.append(_check(f"sample size {cond}", "FAIL" if thin else "PASS",
                             f"{scored} scored, need {policy['min_cases_per_condition']}",
                             fix if thin and cond not in no_go else None))
        lower = ci[0] if ci else 0.0
        if cluster_ci is not None:
            lower = min(lower, cluster_ci[0])
        weak = ci is None or lower < policy["min_pass_rate"]
        review |= weak
        low = ci[0] if ci else "n/a"
        lower_detail = f"{low}, bar {policy['min_pass_rate']}"
        if cluster_ci is not None:
            lower_detail = (f"Wilson [{ci[0]}, {ci[1]}], by clip [{cluster_ci[0]}, {cluster_ci[1]}], "
                            f"lower {lower}, bar {policy['min_pass_rate']}")
        elif cluster_note is not None:
            lower_detail = f"{low}, {cluster_note}, bar {policy['min_pass_rate']}"
        checks.append(_check(f"Wilson lower bound {cond}", "FAIL" if weak else "PASS",
                             lower_detail,
                             fix if weak and cond not in no_go else None))
    share = unscored / len(steps) if steps else 1.0
    bad_share = share > policy["max_unscored_share"]
    review |= bad_share
    checks.append(_check("unscored share", "FAIL" if bad_share else "PASS",
                         f"{unscored}/{len(steps)} = {share:.3f}, max {policy['max_unscored_share']}",
                         f"resolve UNKNOWN and ERROR cases ({unscored} of {len(steps)}) to at most "
                         f"{policy['max_unscored_share'] * 100:g} percent" if bad_share else None))
    need_pct = f"{policy['min_second_annotator_share'] * 100:g}"
    annot_fix = f"add a second annotator on at least {need_pct} percent of cases and run compare-labels"
    if agreement is None:
        review = True
        checks.append(_check("second annotator coverage", "FAIL", "no agreement file given", annot_fix))
        checks.append(_check("annotator kappa", "FAIL", "no agreement file given", annot_fix))
    else:
        cases = len({(s.get("case") or {}).get("id") for s in steps}) or 1
        cover = agreement["cases_compared"] / cases
        kappa = agreement["visibility_kappa"]
        low_cover, low_kappa = cover < policy["min_second_annotator_share"], kappa < policy["min_kappa"]
        review |= low_cover or low_kappa
        checks.append(_check("second annotator coverage", "FAIL" if low_cover else "PASS",
                             f"{agreement['cases_compared']}/{cases} = {cover:.3f}, min "
                             f"{policy['min_second_annotator_share']}", annot_fix if low_cover else None))
        checks.append(_check("annotator kappa", "FAIL" if low_kappa else "PASS",
                             f"{kappa}, min {policy['min_kappa']}",
                             f"discuss the disagreements until kappa is at least {policy['min_kappa']}"
                             if low_kappa else None))
    not_live = run.get("mode") not in LIVE_MODES
    review |= not_live
    checks.append(_check("live evidence", "FAIL" if not_live else "PASS", f"mode {run.get('mode')}",
                         "re-run against the live model so the evidence is not a stand-in" if not_live else None))
    ds_id = str(dataset.get("id"))
    overlap = TRAINING_OVERLAP.get(ds_id, UNKNOWN_OVERLAP)
    if not policy["require_no_training_overlap"]:
        checks.append(_check("training overlap", "NA", "not required by policy"))
    elif overlap == NOT_SEEN:
        checks.append(_check("training overlap", "PASS", f"{ds_id}: not seen in training"))
    else:
        said = "likely seen in SAM training" if overlap == LIKELY_SEEN else "unknown if seen in SAM training"
        review = True
        checks.append(_check("training overlap", "FAIL", f"{ds_id}: {said}",
                             "add photos you took yourself after the model release, or document that "
                             "the model never saw this set"))
    decision = NO_GO if no_go else NEEDS_REVIEW if review else GO_CANDIDATE
    fixes = [c["fix"] for c in checks if c["status"] == "FAIL" and c["fix"]]
    return {**base, "decision": decision, "checks": checks, "next_experiments": sorted(set(fixes))}


def evaluate_file(runs_dir: Path, run_id: str, policy: dict[str, Any],
                  agreement: dict[str, Any] | None = None) -> dict[str, Any]:
    if not RUN_ID.match(run_id):
        raise ValueError("invalid run id")
    path = runs_dir / f"{run_id}.json"
    if not path.is_file():
        raise FileNotFoundError(run_id)
    raw = path.read_bytes()
    return evaluate(json.loads(raw.decode("utf-8")), policy, agreement, hashlib.sha256(raw).hexdigest())


def load_agreement(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases_compared"), int) or \
            not isinstance(data.get("visibility_kappa"), int | float):
        raise TypeError("agreement file needs cases_compared and visibility_kappa (compare-labels output)")
    return data


def render(report: dict[str, Any], fmt: str = "text") -> str:
    if fmt == "json":
        return json.dumps(report, indent=2, sort_keys=True)
    md = fmt == "markdown"
    h = (lambda t: f"## {t}") if md else (lambda t: t.upper())
    bullet = "- " if md else "  "
    lines = [("# " if md else "") + f"Release Gate decision: {report['decision']}"]
    if report.get("reason"):
        lines += ["", f"Evaluated nothing else. Reason: {report['reason']}."]
    if report["checks"]:
        lines += ["", h("Checks")] + [f"{bullet}{c['status']:<4} {c['name']}: {c['detail']}" for c in report["checks"]]
    if report["failing"]:
        lines += ["", h("Failing conditions")] + [bullet + f for f in report["failing"]]
    lines += ["", h("Recommended next experiments")]
    lines += [bullet + n for n in report["next_experiments"]] or [bullet + "none"]
    t = report["traceability"]
    lines += ["", h("Traceability")] + [f"{bullet}{k}: {t[k]}" for k in sorted(t)]
    lines += ["", h("Policy used")] + [f"{bullet}{k}: {json.dumps(v)}" for k, v in sorted(report["policy"].items())]
    lines += ["", report["notice"]]
    return "\n".join(lines)
