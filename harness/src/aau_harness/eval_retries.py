"""Retain sequential retry evidence while normalizing one observation per logical task."""

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_import import import_observations
from .eval_operations import validate_operating_measurements


FILES = {"plan.json", "ledger.json", "recording.json", "evaluation.json", "accounting.json", "manifest.json"}
BOUNDARY = ("Offline accounting of declared sequential retries, not an executed evaluation or permission to retry. "
            "One scenario-repeat observation represents one logical task, not each underlying call. Attempt IDs, "
            "counts, order, disjoint costs, whole-task timings, scores, and context are unverified declarations. "
            "A timeout or failure can still have side effects. Metric reducers are reviewer choices, not inferred "
            "ground truth: last can hide earlier failures; min/max require coverage on every attempt. Missing "
            "measurements remain unknown. Costs and API counts include every declared attempt only when coverage "
            "is complete; partial observed sums are not full totals. Whole-task latency must be supplied separately "
            "and is never the sum of call durations or just the final call. Backoff, queueing, and overhead are not "
            "inferred. Only sequential attempts with non-overlapping accounting scopes are supported; nested spans, "
            "parallel branches, hedged requests, and mixed currencies/cost bases must not be flattened into this "
            "contract. No price lookups, invoice verification, scoring, model calls, or uploads. Missing external "
            "events cannot be detected when the declarations are also changed. Retained JSON values are not original "
            "file bytes. Hashes are not signatures. Inspect identifiers and all source values before sharing; no "
            "sanitization or deployment approval is performed.")


def _bounded(value):
    try:
        json.dumps(value, allow_nan=False)
        if len(rendered(value)) > MAX_JSON_BYTES:
            raise AgentBomError("retry accounting JSON exceeds 2 MB")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise AgentBomError("retry accounting requires bounded finite JSON values") from exc


def _sum(values):
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise AgentBomError("retry accounting sum exceeds finite numeric range") from exc
    if not math.isfinite(result):
        raise AgentBomError("retry accounting sum exceeds finite numeric range")
    return result


def retry_payloads(plan: dict, ledger: dict) -> tuple[dict, dict[str, bytes]]:
    _bounded(plan)
    _bounded(ledger)
    required = {"plan_version", "source_label", "scenario_ids", "n_repeats", "metric_reducers", "attempt_scope"}
    if not isinstance(plan, dict) or not required <= set(plan) or set(plan) - required - {"evaluation_context"}:
        raise AgentBomError("retry plan requires only documented fields")
    if plan["plan_version"] != "aau-retry-accounting/1.0" or plan["attempt_scope"] != "sequential_disjoint":
        raise AgentBomError("retry accounting requires version 1.0 and sequential_disjoint attempt scope")
    reducers = plan["metric_reducers"]
    if (not isinstance(reducers, dict) or not 1 <= len(reducers) <= 100
            or any(not isinstance(key, str) or not key.strip() or len(key) > 200
                   or not isinstance(value, str) or value not in ("min", "max", "last") for key, value in reducers.items())):
        raise AgentBomError("declare 1 to 100 named metric reducers: min, max, or last")
    if (not isinstance(ledger, dict) or set(ledger) != {"ledger_version", "tasks"}
            or ledger["ledger_version"] != "aau-task-attempt-ledger/1.0"
            or not isinstance(ledger["tasks"], list) or not 1 <= len(ledger["tasks"]) <= 10000):
        raise AgentBomError("ledger requires version 1.0 and 1 to 10000 tasks")
    observations, details, identities = [], [], set()
    for task in ledger["tasks"]:
        required = {"scenario_id", "repeat", "attempt_count", "attempts"}
        if not isinstance(task, dict) or not required <= set(task) or set(task) - required - {"elapsed_s"}:
            raise AgentBomError("task requires scenario_id, repeat, attempt_count, attempts and optional elapsed_s")
        count, attempts = task["attempt_count"], task["attempts"]
        if type(count) is not int or not 1 <= count <= 100 or not isinstance(attempts, list) or len(attempts) != count:
            raise AgentBomError("each task must cover its declared 1 to 100 attempts")
        indexed = {}
        for attempt in attempts:
            required = {"attempt_id", "attempt_index", "metrics"}
            if (not isinstance(attempt, dict) or not required <= set(attempt)
                    or set(attempt) - required - {"cost_usd", "n_api_calls", "latency_s"}):
                raise AgentBomError("attempt requires identity, index, metrics and only optional operating fields")
            identity, index = attempt["attempt_id"], attempt["attempt_index"]
            if (not isinstance(identity, str) or not identity.strip() or len(identity) > 200 or identity in identities
                    or type(index) is not int or not 0 <= index < count or index in indexed):
                raise AgentBomError("attempt IDs must be globally unique and indices must cover 0 through count-1")
            identities.add(identity)
            if len(identities) > 10000:
                raise AgentBomError("ledger exceeds 10000 attempts")
            metrics = attempt["metrics"]
            if (not isinstance(metrics, dict) or not set(metrics) <= set(reducers)
                    or any(type(value) not in (int, float) or not -sys.float_info.max <= value <= sys.float_info.max
                           for value in metrics.values())):
                raise AgentBomError("attempt metrics must be declared, finite numeric values; omit unknown scores")
            validate_operating_measurements([attempt])
            indexed[index] = attempt
        ordered = [indexed[index] for index in range(count)]
        row = {"scenario_id": task["scenario_id"], "repeat": task["repeat"], "metrics": {}}
        coverage = {}
        for metric, reducer in sorted(reducers.items()):
            observed = [a["metrics"][metric] for a in ordered if metric in a["metrics"]]
            coverage[metric] = {"reporting_attempts": len(observed), "declared_attempts": count,
                                "reducer": reducer}
            if reducer == "last":
                if metric in ordered[-1]["metrics"]:
                    row["metrics"][metric] = ordered[-1]["metrics"][metric]
            elif len(observed) == count:
                row["metrics"][metric] = (min if reducer == "min" else max)(observed)
        operating = {}
        for field in ("cost_usd", "n_api_calls"):
            values = [a[field] for a in ordered if field in a]
            total = sum(values) if field == "n_api_calls" else _sum(values)
            operating[field] = {"reporting_attempts": len(values), "declared_attempts": count,
                                "observed_sum": total if values else None,
                                "complete_total": total if len(values) == count else None}
            if len(values) == count:
                row[field] = total
        if "elapsed_s" in task:
            validate_operating_measurements([{"latency_s": task["elapsed_s"]}])
            observed_duration = _sum(a["latency_s"] for a in ordered if "latency_s" in a)
            elapsed = task["elapsed_s"]
            if elapsed < observed_duration and not math.isclose(elapsed, observed_duration, rel_tol=1e-12, abs_tol=1e-12):
                raise AgentBomError("whole-task elapsed_s is shorter than known sequential attempt durations")
            row["latency_s"] = elapsed
        observations.append(row)
        details.append({"scenario_id": task["scenario_id"], "repeat": task["repeat"], "attempt_count": count,
                        "retry_count": count - 1, "metric_coverage": coverage, "operating": operating,
                        "whole_task_latency_s": task.get("elapsed_s")})
    recording = {"format_version": "aau-recorded-observations/1.1",
                 **{key: deepcopy(plan[key]) for key in ("source_label", "scenario_ids", "n_repeats")},
                 "observations": observations,
                 **({"evaluation_context": deepcopy(plan["evaluation_context"])} if "evaluation_context" in plan else {})}
    # Validates the complete declared scenario/repeat census and metric/operating bounds.
    evaluation = import_observations(recording)
    recording["observations"] = sorted(observations, key=lambda r: (r["scenario_id"], r["repeat"]))
    # Bind the canonical task order in both the recording and imported provenance.
    evaluation = import_observations(recording)
    report = {"report_version": "aau-retry-accounting-report/1.0", "plan_sha256": digest(plan),
              "ledger_sha256": digest(ledger), "recording_sha256": digest(recording), "evaluation_sha256": digest(evaluation),
              "unit": "logical_task_per_scenario_repeat", "task_count": len(observations),
              "attempt_count": len(identities), "retry_count": len(identities) - len(observations),
              "tasks_with_retries": sum(t["retry_count"] > 0 for t in details),
              "last_only_metrics": sorted(name for name, reducer in reducers.items() if reducer == "last"),
              "unreported_task_metrics": sorted(set(reducers) - set(evaluation["metric_coverage"])),
              "tasks": sorted(details, key=lambda r: (r["scenario_id"], r["repeat"])), "boundary": BOUNDARY}
    files = {name: rendered(value) for name, value in (("plan.json", plan), ("ledger.json", ledger),
             ("recording.json", recording), ("evaluation.json", evaluation), ("accounting.json", report))}
    files["manifest.json"] = rendered({"pack_version": "aau-retry-accounting-pack/1.0",
                                      "files": {name: digest(value) for name, value in sorted(files.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in files.values()):
        raise AgentBomError("retry accounting pack member exceeds 2 MB")
    return report, files


def create_retry_pack(plan: dict, ledger: dict, directory: Path) -> dict:
    if directory.exists() or directory.is_symlink():
        raise AgentBomError("refusing to overwrite retry accounting destination")
    report, files = retry_payloads(plan, ledger)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (directory / name).open("xb") as stream:
            stream.write(value)
    return report


def verify_retry_pack(directory: Path, *, evaluation_path: Path | None = None) -> dict:
    if directory.is_symlink() or not directory.is_dir() or {p.name for p in directory.iterdir()} != FILES:
        raise AgentBomError("retry accounting requires the exact six-file set in a real directory")
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError("retry accounting member must be a regular non-symlink file within 2 MB")
    report, expected = retry_payloads(load_json(directory / "plan.json"), load_json(directory / "ledger.json"))
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f"retry accounting member does not recompute: {name}")
    if evaluation_path is not None and rendered(load_json(evaluation_path)) != expected["evaluation.json"]:
        raise AgentBomError("downstream evaluation does not match verified retry accounting")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aau retry-eval", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("plan", type=Path)
    create.add_argument("ledger", type=Path)
    create.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--evaluation", type=Path, help="also bind the evaluation in a downstream dossier")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_retry_pack(load_json(args.plan), load_json(args.ledger), args.out)
            report = verify_retry_pack(args.out)
        else:
            report = verify_retry_pack(args.directory, evaluation_path=args.evaluation)
        print(f"Retry accounting verified: {report['task_count']} logical tasks, {report['attempt_count']} declared attempts; not approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
