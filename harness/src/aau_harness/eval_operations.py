"""Describe recorded operating costs and latency without hiding failed attempts."""

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_repeatability import review_repeatability


COST_BASES = ("estimate", "charge", "synthetic", "unknown")


def _coverage(rows: list[dict], field: str) -> dict:
    count = sum(field in row for row in rows)
    return {"status": "complete" if count == len(rows) else "partial" if count else "unavailable",
            "reporting_observations": count, "declared_observations": len(rows)}


def _summary(rows: list[dict], passing: set[tuple[str, int]]) -> dict:
    n, passed = len(rows), sum((row["scenario_id"], row["repeat"]) in passing for row in rows)
    cost = _coverage(rows, "cost_usd")
    latency = _coverage(rows, "latency_s")
    calls = _coverage(rows, "n_api_calls")
    try:
        observed_cost = math.fsum(row["cost_usd"] for row in rows if "cost_usd" in row) if cost["reporting_observations"] else None
        complete_cost = cost["status"] == "complete"
        cost.update(
            sum_reported_usd=observed_cost,
            total_usd=observed_cost if complete_cost else None,
            mean_per_attempt_usd=observed_cost / n if complete_cost else None,
            total_per_passing_attempt_usd=observed_cost / passed if complete_cost and passed else None,
            spent_on_failed_attempts_usd=math.fsum(row["cost_usd"] for row in rows
                if (row["scenario_id"], row["repeat"]) not in passing) if complete_cost else None,
            unit_cost_unavailable_reason="incomplete_cost_coverage" if not complete_cost else
                "no_passing_attempts" if not passed else None)
        values = sorted(row["latency_s"] for row in rows if "latency_s" in row)
        complete_latency = latency["status"] == "complete"
        latency.update(p50_s=statistics.median(values) if complete_latency else None,
                       p95_s=values[(95 * n + 99) // 100 - 1] if complete_latency else None,
                       max_s=values[-1] if complete_latency else None)
        observed_calls = sum(row["n_api_calls"] for row in rows if "n_api_calls" in row) if calls["reporting_observations"] else None
        calls.update(sum_reported=observed_calls, total=observed_calls if calls["status"] == "complete" else None)
        # Fail rather than publish Infinity after valid but extreme input values.
        for section in (cost, latency):
            if any(type(value) is float and not math.isfinite(value) for value in section.values()):
                raise ValueError("nonfinite operating summary")
    except (ValueError, OverflowError) as exc:
        raise AgentBomError("operating statistics exceed finite numeric range") from exc
    return {"attempt_count": n, "passing_attempt_count": passed,
            "failing_attempt_count": n - passed, "cost": cost, "latency": latency, "api_calls": calls}


def review_operations(source: dict, *, criteria: list[dict], cost_basis: str) -> dict:
    if cost_basis not in COST_BASES:
        raise AgentBomError("cost_basis must be estimate, charge, synthetic, or unknown")
    repeat_review = review_repeatability(source, criteria=criteria, draw_sizes=[1])
    rows = sorted(source["results"], key=lambda row: (row["scenario_id"], row["repeat"]))
    for row in rows:
        for field in ("cost_usd", "latency_s", "n_api_calls"):
            if field not in row:
                continue  # Absent means unknown, never zero.
            value = row[field]
            if field == "n_api_calls":
                valid = type(value) is int and 0 <= value <= 10**12
            else:
                valid = type(value) in (int, float) and 0 <= value <= sys.float_info.max
            if not valid:
                raise AgentBomError(f"{field} must be finite nonnegative numeric data (API calls: integer up to 10^12); omit unknown fields")
    passing = {(row["scenario_id"], repeat) for row in repeat_review["scenarios"] for repeat in row["passing_repeat_ids"]}
    overall = _summary(rows, passing)
    scenarios = []
    for assessment in repeat_review["scenarios"]:
        identity = assessment["scenario_id"]
        selected = [row for row in rows if row["scenario_id"] == identity]
        scenarios.append({"scenario_id": identity, **_summary(selected, passing), "failures": assessment["failures"]})
    warnings = [
        "Cost basis is a caller declaration, not verified pricing, a verified invoice, or an attestation.",
        "Zero recorded cost does not establish a free service. Raw values may already be rounded; no precision is recovered.",
        "Failure costs stay in the numerator. Passing attempts are repeated scored observations, not distinct people served or realized business outcomes.",
    ]
    for field, label in (("cost", "cost"), ("latency", "latency"), ("api_calls", "API-call")):
        if overall[field]["status"] != "complete":
            warnings.append(f"Incomplete {label} coverage: full-sample derived statistics remain null, not zero or complete-case estimates.")
    if len(rows) < 20:
        warnings.append("Fewer than 20 observations: the nearest-rank p95 is the maximum and is not a stable tail-risk estimate.")
    elif source["n_repeats"] < 20:
        warnings.append("Each scenario has fewer than 20 repeats: its p95 is the recorded maximum even though the overall sample is larger.")
    if repeat_review["source_audit"]["status"] != "consistent":
        warnings.append("Stored metric summaries disagree with recomputation; pass/fail uses observations, not the stored headline.")
    return {
        "report_version": "aau-evaluation-operations/1.0", "source_sha256": digest(source),
        "declared_cost_basis": cost_basis, "currency": "USD",
        "criteria": repeat_review["criteria"], "scenario_count": source["n_scenarios"],
        "repeat_count": source["n_repeats"], "overall": overall, "scenarios": scenarios,
        "source_metric_audit": repeat_review["source_audit"],
        "unreviewed_metrics": repeat_review["unreviewed_metrics"], "warnings": warnings,
        "method": {"unit": "recorded scenario-repeat attempt",
                   "pass_condition": "every supplied observation criterion passes on the same attempt",
                   "unit_cost": "sum of all recorded attempt costs, including failures, divided by jointly passing attempt count",
                   "p50_latency": "median of all recorded attempt latencies, including failures",
                   "p95_latency": "nearest rank: sorted latency at ceil(0.95 * attempt_count), one-based",
                   "missing_data": "field-specific coverage; full-sample totals, ratios and quantiles require complete coverage",
                   "arithmetic": "finite floating-point summaries from recorded values; no precision inferred beyond source",
                   "stored_operational_summaries": "not reused or audited; source rows may have been rounded differently"},
        "boundary": "Descriptive accounting of supplied observations, not a cost forecast, invoice reconciliation, SLO assessment, cost-efficiency ranking, or deployment approval. No provider prices, exchange rates, measurements, or missing values are fetched or invented. Costs exclude anything absent from the source, including infrastructure, human review, downstream tools, and overhead; not fully loaded cost or ROI. Scoring validity, runtime authenticity, timing instrumentation, independence, retry chronology, and representativeness are unverified. A failed attempt may still have incurred effects; this report does not authorize retries. No underlying evaluation is modified. Scenario IDs, scores, cost and latency data can be sensitive; review before sharing.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau operating-eval", description=__doc__)
    parser.add_argument("evaluation", type=Path)
    parser.add_argument("--criterion", nargs=3, action="append", required=True,
                        metavar=("METRIC", "DIRECTION", "LIMIT"))
    parser.add_argument("--cost-basis", choices=COST_BASES, required=True,
                        help="declared basis only; no invoice or price verification is performed")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        try:
            criteria = [{"metric": metric, "direction": direction, "limit": json.loads(limit)}
                        for metric, direction, limit in args.criterion]
        except (ValueError, RecursionError) as exc:
            raise AgentBomError("criterion limits must be numeric") from exc
        report = review_operations(load_json(args.evaluation), criteria=criteria, cost_basis=args.cost_basis)
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("operating report exceeds verification size limit")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("operating report does not recompute")
        else:
            write_json(report, args.out)
        counts = report["overall"]
        print(f"Operating review: {counts['passing_attempt_count']}/{counts['attempt_count']} attempts meet criteria; declared cost basis {args.cost_basis}. Not a forecast.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
