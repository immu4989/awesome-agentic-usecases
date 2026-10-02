"""Offline, explanatory assessment of supplied public-service contracts and traces."""

import argparse
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .agent_bom import AgentBomError, digest, load_json, rendered, write_json
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau public-value", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    assess = sub.add_parser("assess", help="explain failed obligations in a supplied service trace")
    verify = sub.add_parser("verify", help="recompute a saved assessment without executing service code")
    verify.add_argument("report", type=Path)
    for command in (assess, verify):
        command.add_argument("contract", type=Path)
        command.add_argument("trace", type=Path)
    assess.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = assess_public_value(load_json(args.contract), load_json(args.trace))
        if args.command == "assess":
            write_json(report, args.out)
        elif rendered(load_json(args.report)) != rendered(report):
            raise AgentBomError("public-value report does not recompute")
        print(f"{report['status']}: {len(report['findings'])} failed obligations")
        return 0 if report["status"] == "evidence_passed" else 1
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
