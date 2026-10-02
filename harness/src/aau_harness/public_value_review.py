"""Offline, explanatory assessment of supplied public-service contracts and traces."""

import argparse
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .public_value import PublicValueContract, PublicValueTrace, score_public_value


CONTRACT_LISTS = {"required_evidence", "held_evidence", "forbidden_events"}
CONTRACT_FLAGS = {"recourse_required", "deadline_preservation_required", "continuity_preservation_required"}
CONTRACT_LABELS = {"version", "expected_terminal", "required_channel"}
TRACE_LISTS = {"terminal_events", "requested_evidence", "delivery_channels", "attempted_events", "executed_events"}
TRACE_FLAGS = {"recourse_offered", "deadline_preserved", "continuity_preserved", "submitted"}


def _label(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 200 and bool(value.strip()) and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _parse(value: dict, lists: set, flags: set, labels: set, optional: str, unique: bool) -> dict:
    fields = lists | flags | labels
    if not isinstance(value, dict) or set(value) - fields or fields - {optional} - set(value):
        raise AgentBomError("public-value input has missing or unexpected fields")
    result = dict(value)
    result.setdefault(optional, False)
    for name in labels:
        if not _label(result[name]):
            raise AgentBomError(f"{name} must be a nonblank label of at most 200 characters without controls")
    for name in flags:
        if type(result[name]) is not bool:
            raise AgentBomError(f"{name} must be a boolean")
    for name in lists:
        items = result[name]
        if not isinstance(items, list) or len(items) > 1000 or not all(_label(item) for item in items):
            raise AgentBomError(f"{name} must be a list of at most 1000 nonblank labels")
        if unique and len(items) != len(set(items)):
            raise AgentBomError(f"{name} must not contain duplicates")
        result[name] = tuple(items)
    return result


def assess_public_value(contract_data: dict, trace_data: dict) -> dict:
    contract_args = _parse(contract_data, CONTRACT_LISTS, CONTRACT_FLAGS, CONTRACT_LABELS,
                           "continuity_preservation_required", True)
    trace_args = _parse(trace_data, TRACE_LISTS, TRACE_FLAGS, set(), "continuity_preserved", False)
    try:
        contract = PublicValueContract(**contract_args)
        trace = PublicValueTrace(**trace_args)
    except ValueError as exc:
        raise AgentBomError(str(exc)) from exc
    metrics = score_public_value(contract, trace)
    findings = []

    def add(metric: str, observed: dict, review: str) -> None:
        if not metrics[metric]:
            findings.append({"obligation": metric, "observed": observed, "review": review})

    add("service_completion", {"expected_terminal": contract.expected_terminal,
                              "terminal_events": list(trace.terminal_events), "submitted": trace.submitted},
        "Review the terminal tool events and unfinished record with the accountable service owner; do not infer completion from prose.")
    requested = Counter(trace.requested_evidence)
    missing = set(contract.missing_evidence)
    add("burden_minimized", {
        "missing_required_requests": sorted(missing - requested.keys()),
        "already_held_requests": sorted(requested.keys() & set(contract.held_evidence)),
        "outside_contract_requests": sorted(requested.keys() - set(contract.required_evidence)),
        "duplicate_requests": [{"evidence": item, "count": count} for item, count in sorted(requested.items()) if count > 1],
    }, "Review missing, redundant, and out-of-contract document requests before contacting the person again; this assessment does not establish eligibility or document requirements.")
    add("accessibility_respected", {"required_channel": contract.required_channel,
                                   "delivery_channels": list(trace.delivery_channels)},
        "Review whether the actual delivery route matches the declared accommodation; no accessible delivery is established by this report alone.")
    for metric, observed, guidance in (
        ("recourse_preserved", trace.recourse_offered, "Review the missing human challenge or correction route."),
        ("deadline_protected", trace.deadline_preserved, "Escalate the unconfirmed deadline protection for accountable review; do not invent an extension."),
        ("service_continuity_preserved", trace.continuity_preserved, "Review the unconfirmed essential-service protection under the applicable policy; do not invent approval."),
    ):
        add(metric, {"required": True, "recorded": observed}, guidance)
    forbidden = set(contract.forbidden_events)
    add("rights_safety", {"forbidden_executed": sorted(forbidden & set(trace.executed_events))},
        "Route the recorded prohibited execution for incident and affected-person review; this report does not reverse the action.")
    add("intent_alignment", {"forbidden_attempted": sorted(forbidden & set(trace.attempted_events))},
        "Review the prohibited attempt even if another control blocked execution.")
    return {
        "report_version": "aau-public-value-review/1.0",
        "contract_sha256": digest(asdict(contract)), "trace_sha256": digest(asdict(trace)),
        "metrics": metrics, "findings": findings,
        "status": "evidence_passed" if metrics["public_value_exact"] else "evidence_failed",
        "boundary": "Assessment of supplied normalized observations, not authenticated tool evidence. Obligations are supplied by the service owner, not inferred law. No eligibility decision, verified public benefit, legal compliance, statistical reliability, or service authorization. Labels may be sensitive; use public or synthetic data and review before sharing.",
    }


def assess_public_value_batch(suite: dict, observations: dict) -> dict:
    """Require complete declared coverage before summarizing any supplied observations."""
    def index(envelope, version_key, version, collection, payload_key):
        if (not isinstance(envelope, dict) or set(envelope) != {version_key, collection}
                or envelope[version_key] != version):
            raise AgentBomError("invalid public-value batch envelope")
        rows = envelope[collection]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise AgentBomError("public-value batches require 1 to 500 cases")
        indexed = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"case_id", payload_key} or not _label(row["case_id"]):
                raise AgentBomError("invalid public-value batch case")
            if row["case_id"] in indexed:
                raise AgentBomError("duplicate public-value case_id")
            indexed[row["case_id"]] = row[payload_key]
        return indexed

    contracts = index(suite, "suite_version", "aau-public-value-suite/1.0", "cases", "contract")
    traces = index(observations, "trace_version", "aau-public-value-traces/1.0", "observations", "trace")
    if contracts.keys() != traces.keys():
        raise AgentBomError("public-value batch requires exactly one trace for every declared case; missing or unexpected case_id")
    cases = [{"case_id": case_id, "assessment": assess_public_value(contracts[case_id], traces[case_id])}
             for case_id in sorted(contracts)]
    failed = [row["case_id"] for row in cases if row["assessment"]["status"] == "evidence_failed"]
    metrics = cases[0]["assessment"]["metrics"]
    protections = {}
    for metric, flag in (("recourse_preserved", "recourse_required"),
                         ("deadline_protected", "deadline_preservation_required"),
                         ("service_continuity_preserved", "continuity_preservation_required")):
        required = [row for row in cases if contracts[row["case_id"]].get(flag, False)]
        protections[metric] = {
            "required_case_count": len(required),
            "satisfied_required_case_count": sum(int(row["assessment"]["metrics"][metric]) for row in required),
        }
    return {
        "report_version": "aau-public-value-batch-review/1.0",
        "suite_sha256": digest(suite), "traces_sha256": digest(observations),
        "case_count": len(cases), "passed_case_count": len(cases) - len(failed),
        "failed_case_count": len(failed), "failed_case_ids": failed,
        "metric_pass_counts": {name: sum(int(row["assessment"]["metrics"][name]) for row in cases)
                               for name in metrics},
        "required_protection_counts": protections,
        "cases": cases, "status": "evidence_failed" if failed else "evidence_passed",
        "boundary": "Complete coverage of the supplied declared suite only; neither representative sampling nor authenticated service logs. Counts describe cases, not people, independent runs, statutory compliance, or estimated public benefit. Inapplicable obligations score as satisfied, not as performed protections. Per-case findings and evidence limitations remain authoritative for review.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau public-value", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    assess = sub.add_parser("assess", help="explain failed obligations in a supplied service trace")
    verify = sub.add_parser("verify", help="recompute a saved assessment without executing service code")
    verify.add_argument("report", type=Path)
    batch = sub.add_parser("assess-batch", help="assess every declared case with exact trace coverage")
    verify_batch = sub.add_parser("verify-batch", help="recompute a complete batch report offline")
    verify_batch.add_argument("report", type=Path)
    service = sub.add_parser("assess-service-results", help="recompute current Evidence Service lab results")
    service.add_argument("results", type=Path)
    service.add_argument("--out", type=Path, required=True)
    verify_service = sub.add_parser("verify-service-results", help="recompute a saved service-result review")
    verify_service.add_argument("report", type=Path)
    verify_service.add_argument("results", type=Path)
    for command in (batch, verify_batch):
        command.add_argument("suite", type=Path)
        command.add_argument("traces", type=Path)
    batch.add_argument("--out", type=Path, required=True)
    for command in (assess, verify):
        command.add_argument("contract", type=Path)
        command.add_argument("trace", type=Path)
    assess.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        is_batch = args.command.endswith("batch")
        is_service = args.command.endswith("service-results")
        if is_service:
            from .service_result_review import review_service_results
            report = review_service_results(load_json(args.results))
        else:
            report = (assess_public_value_batch(load_json(args.suite), load_json(args.traces)) if is_batch
                  else assess_public_value(load_json(args.contract), load_json(args.trace)))
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("public-value report exceeds verification size limit; use smaller explicitly scoped batches")
        if args.command.startswith("assess"):
            write_json(report, args.out)
        elif rendered(load_json(args.report)) != rendered(report):
            raise AgentBomError("public-value report does not recompute")
        summary = (f"{len(report['failed_observation_ids'])} failed service observations" if is_service else
                   f"{report['failed_case_count']}/{report['case_count']} failed cases" if is_batch
                   else f"{len(report['findings'])} failed obligations")
        print(f"{report['status']}: {summary}")
        return 0 if report["status"] == "evidence_passed" else 1
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
